# src/dmh_mr_tool/ui/views/parser_view.py
"""Parser Interface for processing dividend and component data from PDFs and Excel files"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFormLayout,
    QFileDialog, QComboBox, QTextEdit, QLineEdit,
    QMessageBox
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from qfluentwidgets import (
    CardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, ComboBox, CheckBox,
    LineEdit, FluentIcon as FIF, DatePicker, TableWidget
)
from qasync import asyncSlot

from ..views.base_view import BaseInterface, SeparatorWidget
from ui.utils.signal_bus import signalBus
from ui.utils.infobar import raise_error_bar_in_class, createWarningInfoBar, createSuccessInfoBar, createErrorInfoBar
from business.services.parser_service import ParserService
from database.models import ParseTemplateMR, ParseTemplateNZ
from config.settings import CONFIG

import structlog

logger = structlog.get_logger()


class DragDropArea(CardWidget):
    """Drag and drop area for file upload"""

    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # Icon
        icon_label = QLabel("📄", self)
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Text
        text_label = StrongBodyLabel("Drag and drop files here", self)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub_label = CaptionLabel("or click to browse", self)
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Browse button
        self.browseBtn = PushButton("Browse Files", self)
        self.browseBtn.setIcon(FIF.FOLDER)
        self.browseBtn.clicked.connect(self.browseFiles)

        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addWidget(sub_label)
        layout.addWidget(self.browseBtn)

        # Styling - Google-like gray drop area
        self.setStyleSheet("""
            DragDropArea {
                background-color: #f5f5f5;
                border: 2px dashed #dadce0;
                border-radius: 8px;
                min-height: 200px;
            }
            DragDropArea:hover {
                background-color: #f1f3f4;
                border-color: #5f6368;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                DragDropArea {
                    background-color: #e8f0fe;
                    border: 2px dashed #1a73e8;
                    border-radius: 8px;
                    min-height: 200px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            DragDropArea {
                background-color: #f5f5f5;
                border: 2px dashed #dadce0;
                border-radius: 8px;
                min-height: 200px;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.fileDropped.emit(files[0])
        self.dragLeaveEvent(event)

    def browseFiles(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "All Supported (*.pdf *.xlsx *.xls);;PDF Files (*.pdf);;Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.fileDropped.emit(file_path)


class EditablePatternDelegate(QWidget):
    """Widget for editing regex patterns in table cells"""

    patternChanged = Signal(str)

    def __init__(self, initial_pattern="", parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.edit = QLineEdit(initial_pattern)
        self.edit.setToolTip("Double-click to edit pattern")
        self.edit.editingFinished.connect(self.onEditingFinished)
        self.layout.addWidget(self.edit)

        # Initially read-only, double-click to edit
        self.edit.setReadOnly(True)
        self.edit.mouseDoubleClickEvent = self.enableEdit

    def enableEdit(self, event):
        self.edit.setReadOnly(False)
        self.edit.selectAll()
        self.edit.setFocus()

    def onEditingFinished(self):
        self.edit.setReadOnly(True)
        self.patternChanged.emit(self.edit.text())

    def getPattern(self):
        return self.edit.text()


class ParseResultTable(TableWidget):
    """Table widget for displaying parse results"""

    patternChanged = Signal(int, str)  # row, new_pattern
    rowDeleted = Signal(int)  # row

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUI()
        self.hidden_rows = []  # Track which rows are hidden due to None values
        self.pattern_widgets = {}  # Track pattern edit widgets
        self.deleted_rows = set()  # Track deleted rows

    def setupUI(self):
        # Set headers
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Column Name", "Pattern", "Value", "Comment"])

        # Configure table
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    def loadParseResults(self, results: Dict[str, Dict[str, Any]], template_data: Dict[str, str]):
        """Load parse results into the table"""
        self.clear()
        self.setRowCount(0)
        self.hidden_rows.clear()
        self.pattern_widgets.clear()
        self.deleted_rows.clear()

        # Add all columns from column_map
        row_index = 0
        for field_name, field_data in results.items():
            self.insertRow(row_index)

            # Column name
            name_item = QTableWidgetItem(field_data.get('d_desc', field_name))
            name_item.setData(Qt.ItemDataRole.UserRole, field_name)  # Store field name
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row_index, 0, name_item)

            # Pattern (editable via double-click)
            pattern = template_data.get(field_name, '')
            pattern_widget = EditablePatternDelegate(pattern[:50] + '...' if len(pattern) > 50 else pattern)
            pattern_widget.setToolTip(pattern)
            pattern_widget.patternChanged.connect(lambda p, r=row_index: self.onPatternChanged(r, p))
            self.setCellWidget(row_index, 1, pattern_widget)
            self.pattern_widgets[row_index] = pattern_widget

            # Value (editable)
            value = field_data.get('value', '')
            value_item = QTableWidgetItem(str(value) if value is not None else '')
            self.setItem(row_index, 2, value_item)

            # Comment
            comment = field_data.get('comment', '')
            comment_item = QTableWidgetItem(comment)
            comment_item.setFlags(comment_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row_index, 3, comment_item)

            # Hide row if value is None
            if value is None or value == '':
                self.hideRow(row_index)
                self.hidden_rows.append(row_index)

            row_index += 1

    def onPatternChanged(self, row: int, new_pattern: str):
        """Handle pattern change"""
        self.patternChanged.emit(row, new_pattern)

    def showHiddenRows(self, show: bool):
        """Show or hide rows with None values"""
        for row in self.hidden_rows:
            if row not in self.deleted_rows:
                if show:
                    self.showRow(row)
                else:
                    self.hideRow(row)

    def deleteSelectedRow(self):
        """Delete the currently selected row"""
        current_row = self.currentRow()
        if current_row >= 0:
            # Clear value and hide row
            self.item(current_row, 2).setText('')
            self.hideRow(current_row)
            self.deleted_rows.add(current_row)
            self.rowDeleted.emit(current_row)
            return True
        return False

    def addNewRow(self, field_name: str, field_desc: str):
        """Add a new row for a field"""
        row_index = self.rowCount()
        self.insertRow(row_index)

        # Column name
        name_item = QTableWidgetItem(field_desc)
        name_item.setData(Qt.ItemDataRole.UserRole, field_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row_index, 0, name_item)

        # Pattern (empty, editable)
        pattern_widget = EditablePatternDelegate("")
        pattern_widget.patternChanged.connect(lambda p, r=row_index: self.onPatternChanged(r, p))
        self.setCellWidget(row_index, 1, pattern_widget)
        self.pattern_widgets[row_index] = pattern_widget

        # Value (editable)
        value_item = QTableWidgetItem("")
        self.setItem(row_index, 2, value_item)

        # Comment
        comment_item = QTableWidgetItem("Manually added")
        comment_item.setFlags(comment_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row_index, 3, comment_item)

    def getValues(self) -> Dict[str, Any]:
        """Get all values from the table"""
        values = {}
        for row in range(self.rowCount()):
            if not self.isRowHidden(row) and row not in self.deleted_rows:
                name_item = self.item(row, 0)
                if name_item:
                    field_name = name_item.data(Qt.ItemDataRole.UserRole) or name_item.text()
                    value = self.item(row, 2).text() if self.item(row, 2) else ''
                    if value:  # Only include non-empty values
                        values[field_name] = value
        return values

    def getPatterns(self) -> Dict[str, str]:
        """Get all patterns from the table"""
        patterns = {}
        for row in range(self.rowCount()):
            if row not in self.deleted_rows:
                name_item = self.item(row, 0)
                if name_item and row in self.pattern_widgets:
                    field_name = name_item.data(Qt.ItemDataRole.UserRole) or name_item.text()
                    pattern = self.pattern_widgets[row].getPattern()
                    if pattern:
                        patterns[field_name] = pattern
        return patterns


class AddFieldDialog(QDialog):
    """Dialog for adding a new field"""

    def __init__(self, available_fields: List[tuple], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Field")
        self.setModal(True)
        self.setupUI(available_fields)

    def setupUI(self, available_fields):
        layout = QVBoxLayout(self)

        # Field selection
        form = QFormLayout()
        self.fieldCombo = QComboBox(self)
        for field_name, field_desc in available_fields:
            self.fieldCombo.addItem(field_desc, field_name)
        form.addRow("Select Field:", self.fieldCombo)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getSelectedField(self) -> tuple:
        """Get selected field (name, description)"""
        return (
            self.fieldCombo.currentData(),
            self.fieldCombo.currentText()
        )


class HeaderDialog(QDialog):
    """Dialog for collecting header identifiers before submission"""

    def __init__(self, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("Enter Header Information")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.initial_data = initial_data or {}
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)

        # Form layout for inputs
        form = QFormLayout()

        # Client ID
        self.clientIdEdit = LineEdit(self)
        self.clientIdEdit.setText(self.initial_data.get('client_id', ''))
        form.addRow("Client ID:", self.clientIdEdit)

        # Asset ID
        self.assetIdEdit = LineEdit(self)
        self.assetIdEdit.setText(self.initial_data.get('asset_id', ''))
        form.addRow("Asset ID:", self.assetIdEdit)

        # Ex Date
        self.exDatePicker = DatePicker(self)
        if 'ex_date' in self.initial_data:
            self.exDatePicker.setDate(self.initial_data['ex_date'])
        form.addRow("Ex Date:", self.exDatePicker)

        # Pay Date
        self.payDatePicker = DatePicker(self)
        if 'pay_date' in self.initial_data:
            self.payDatePicker.setDate(self.initial_data['pay_date'])
        form.addRow("Pay Date:", self.payDatePicker)

        # MR Income Rate
        self.incomeRateEdit = LineEdit(self)
        self.incomeRateEdit.setText(str(self.initial_data.get('mr_income_rate', '')))
        form.addRow("MR Income Rate:", self.incomeRateEdit)

        # Type
        self.typeCombo = ComboBox(self)
        self.typeCombo.addItems(["Other", "Last Actual", "Template - PIII"])
        if 'type' in self.initial_data:
            self.typeCombo.setCurrentText(self.initial_data['type'])
        form.addRow("Type:", self.typeCombo)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getValues(self) -> Dict[str, Any]:
        """Get all entered values"""
        return {
            'client_id': self.clientIdEdit.text(),
            'asset_id': self.assetIdEdit.text(),
            'ex_date': self.exDatePicker.getDate(),
            'pay_date': self.payDatePicker.getDate(),
            'mr_income_rate': float(self.incomeRateEdit.text()) if self.incomeRateEdit.text() else 0,
            'type': self.typeCombo.currentText()
        }


class ParserInterface(BaseInterface):
    """Parser Interface for processing source documents"""

    # Signal to send data to MR Update Interface
    dataSubmitted = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(
            title="Parser",
            subtitle="Parse dividend and component data from source documents",
            parent=parent
        )
        self.setObjectName('parserInterface')
        self.parser_service = ParserService()
        self.current_file_path = None
        self.current_file_content = None  # Store file content for re-parsing
        self.current_template = None
        self.parse_results = {}
        self.initUI()
        self.connectSignalToSlot()

    def initUI(self):
        """Initialize the user interface"""
        self.body_layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(self.body_layout)

        # File upload section
        self.addFileUploadSection()

        # Template selection
        self.addTemplateSelection()

        # Parse results table
        self.addParseResultsTable()

        # Control buttons
        self.addControlButtons()

        # Batch folder processing
        self.addBatchProcessing()

        self.addPageBody("", widget, stretch=1)

    def addFileUploadSection(self):
        """Add file upload section with drag and drop"""
        self.dragDropArea = DragDropArea(self)
        self.dragDropArea.fileDropped.connect(self.onFileSelected)

        # Current file display
        self.currentFileLabel = BodyLabel("No file selected", self)

        title = StrongBodyLabel("Upload Source Document")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(self.dragDropArea)
        self.body_layout.addWidget(self.currentFileLabel)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addTemplateSelection(self):
        """Add template selection section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # Template combo box
        self.templateCombo = ComboBox(widget)
        self.templateCombo.setMinimumWidth(200)
        self.loadTemplates()

        # Parse button
        self.parseBtn = PrimaryPushButton("Parse Document", widget)
        self.parseBtn.setIcon(FIF.SYNC)
        self.parseBtn.clicked.connect(self.onParse)
        self.parseBtn.setEnabled(False)

        layout.addWidget(BodyLabel("Template:", widget))
        layout.addWidget(self.templateCombo)
        layout.addWidget(self.parseBtn)
        layout.addStretch()

        title = StrongBodyLabel("Select Parsing Template")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addParseResultsTable(self):
        """Add parse results table"""
        # Table widget
        self.resultsTable = ParseResultTable(self)
        self.resultsTable.setMinimumHeight(300)
        self.resultsTable.patternChanged.connect(self.onPatternChanged)
        self.resultsTable.rowDeleted.connect(self.onRowDeleted)

        # Show hidden rows checkbox
        self.showHiddenCheck = CheckBox("Show empty fields", self)
        self.showHiddenCheck.toggled.connect(self.resultsTable.showHiddenRows)

        # Add row button
        self.addRowBtn = PushButton("Add Field", self)
        self.addRowBtn.setIcon(FIF.ADD)
        self.addRowBtn.clicked.connect(self.onAddRow)

        # Delete row button
        self.deleteRowBtn = PushButton("Delete Selected", self)
        self.deleteRowBtn.setIcon(FIF.DELETE)
        self.deleteRowBtn.clicked.connect(self.onDeleteRow)

        controls = QWidget()
        layout = QHBoxLayout(controls)
        layout.addWidget(self.showHiddenCheck)
        layout.addWidget(self.addRowBtn)
        layout.addWidget(self.deleteRowBtn)
        layout.addStretch()

        title = StrongBodyLabel("Parse Results")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(controls)
        self.body_layout.addWidget(self.resultsTable)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addControlButtons(self):
        """Add control buttons"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # Submit button
        self.submitBtn = PrimaryPushButton("Submit to MR Update", widget)
        self.submitBtn.setIcon(FIF.SEND)
        self.submitBtn.clicked.connect(self.onSubmit)
        self.submitBtn.setEnabled(False)

        # Clear button
        self.clearBtn = PushButton("Clear", widget)
        self.clearBtn.setIcon(FIF.DELETE)
        self.clearBtn.clicked.connect(self.onClear)

        # Save template button
        self.saveTemplateBtn = PushButton("Save as Template", widget)
        self.saveTemplateBtn.setIcon(FIF.SAVE)
        self.saveTemplateBtn.clicked.connect(self.onSaveTemplate)
        self.saveTemplateBtn.setEnabled(False)

        layout.addWidget(self.submitBtn)
        layout.addWidget(self.clearBtn)
        layout.addWidget(self.saveTemplateBtn)
        layout.addStretch()

        self.body_layout.addWidget(widget)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addBatchProcessing(self):
        """Add batch folder processing section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # Folder path input
        self.folderPathEdit = LineEdit(widget)
        self.folderPathEdit.setPlaceholderText("Enter folder path for batch processing")
        self.folderPathEdit.setMinimumWidth(300)

        # Browse folder button
        self.browseFolderBtn = PushButton("Browse", widget)
        self.browseFolderBtn.setIcon(FIF.FOLDER)
        self.browseFolderBtn.clicked.connect(self.onBrowseFolder)

        # Batch process button
        self.batchProcessBtn = PrimaryPushButton("Batch Process", widget)
        self.batchProcessBtn.setIcon(FIF.PLAY)
        self.batchProcessBtn.clicked.connect(self.onBatchProcess)

        layout.addWidget(BodyLabel("Folder Path:", widget))
        layout.addWidget(self.folderPathEdit)
        layout.addWidget(self.browseFolderBtn)
        layout.addWidget(self.batchProcessBtn)
        layout.addStretch()

        title = StrongBodyLabel("Batch Processing (Hi-Trust UR Template)")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)

    def connectSignalToSlot(self):
        """Connect signals to slots"""
        # Connect to parser complete signal
        if hasattr(signalBus, 'parserCompleteSignal'):
            signalBus.parserCompleteSignal.connect(self.onParseComplete)

    def loadTemplates(self):
        """Load available templates"""
        templates = self.parser_service.get_available_templates()
        self.templateCombo.clear()
        self.templateCombo.addItems(templates)

    def onFileSelected(self, file_path: str):
        """Handle file selection"""
        self.current_file_path = file_path
        self.currentFileLabel.setText(f"Selected: {os.path.basename(file_path)}")
        self.parseBtn.setEnabled(True)

        # Auto-select template based on file name
        template = self.parser_service.get_template_by_file_pattern(os.path.basename(file_path))
        if template:
            index = self.templateCombo.findText(template)
            if index >= 0:
                self.templateCombo.setCurrentIndex(index)

    @asyncSlot()
    @raise_error_bar_in_class
    async def onParse(self):
        """Handle parse button click"""
        if not self.current_file_path:
            createWarningInfoBar(self, "No File", "Please select a file to parse")
            return

        try:
            self.parseBtn.setEnabled(False)
            template_name = self.templateCombo.currentText()

            # Parse the file
            results = await self.parser_service.parse_file(
                self.current_file_path,
                template_name
            )

            if results:
                self.parse_results = results
                self.current_template = template_name

                # Load results into table
                template_data = self.parser_service.get_template_data(template_name)
                self.resultsTable.loadParseResults(results, template_data)

                self.submitBtn.setEnabled(True)
                self.saveTemplateBtn.setEnabled(True)

                createSuccessInfoBar(self, "Parse Complete", "Document parsed successfully")
            else:
                createWarningInfoBar(self, "Parse Failed", "No data could be extracted")

        except Exception as e:
            logger.error(f"Parse error: {e}")
            raise
        finally:
            self.parseBtn.setEnabled(True)

    @asyncSlot()
    async def onPatternChanged(self, row: int, new_pattern: str):
        """Handle pattern change - re-parse with new pattern"""
        if not self.current_file_path or not new_pattern:
            return

        try:
            # Get field name from row
            name_item = self.resultsTable.item(row, 0)
            if not name_item:
                return

            field_name = name_item.data(Qt.ItemDataRole.UserRole) or name_item.text()

            # Re-parse just this field
            import pdfplumber
            full_text = ""

            if self.current_file_path.lower().endswith('.pdf'):
                with pdfplumber.open(self.current_file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            full_text += page_text + "\n"

            # Apply new pattern
            try:
                match = re.search(new_pattern, full_text, re.MULTILINE | re.DOTALL)
                if match:
                    value = match.group(1) if match.groups() else match.group(0)
                    value = value.strip()

                    # Update value in table
                    self.resultsTable.item(row, 2).setText(str(value))

                    # Update comment
                    self.resultsTable.item(row, 3).setText("Pattern updated")
                else:
                    self.resultsTable.item(row, 2).setText("")
                    self.resultsTable.item(row, 3).setText("No match found")

            except re.error as e:
                self.resultsTable.item(row, 3).setText(f"Pattern error: {str(e)}")

        except Exception as e:
            logger.error(f"Error applying pattern: {e}")

    def onRowDeleted(self, row: int):
        """Handle row deletion"""
        logger.info(f"Row {row} deleted")

    def onAddRow(self):
        """Add a new row to the results table"""
        # Get available fields not already in table
        all_fields = self.parser_service.get_available_fields()

        # Get current fields in table
        current_fields = set()
        for row in range(self.resultsTable.rowCount()):
            name_item = self.resultsTable.item(row, 0)
            if name_item:
                current_fields.add(name_item.text())

        # Filter available fields
        available = [(k, v['d_desc']) for k, v in self.parser_service.column_map_cache.items()
                     if v['d_desc'] not in current_fields]

        if not available:
            createWarningInfoBar(self, "No Fields", "All available fields are already in the table")
            return

        # Show dialog
        dialog = AddFieldDialog(available, self)
        if dialog.exec():
            field_name, field_desc = dialog.getSelectedField()
            self.resultsTable.addNewRow(field_name, field_desc)

    def onDeleteRow(self):
        """Delete selected row"""
        if self.resultsTable.deleteSelectedRow():
            createSuccessInfoBar(self, "Deleted", "Row deleted successfully")
        else:
            createWarningInfoBar(self, "No Selection", "Please select a row to delete")

    def onSubmit(self):
        """Submit parsed data to MR Update Interface"""
        if not self.parse_results:
            createWarningInfoBar(self, "No Data", "No parsed data to submit")
            return

        # Get values from table
        table_values = self.resultsTable.getValues()

        # Validate the data
        is_valid, errors = self.parser_service.validate_parse_results(
            {k: {'value': v} for k, v in table_values.items()}
        )

        if not is_valid:
            error_msg = "\n".join(errors)
            createErrorInfoBar(self, error_msg, title="Validation Failed")
            return

        # Show header dialog
        dialog = HeaderDialog(self)
        if dialog.exec():
            header_data = dialog.getValues()

            # Prepare submission package
            submission_data = {
                'header': header_data,
                'data': table_values,
                'source_file': self.current_file_path,
                'template': self.current_template,
                'timestamp': datetime.now()
            }

            # Emit signal to MR Update Interface
            self.dataSubmitted.emit(submission_data)

            # Send via signal bus
            signalBus.mrUpdateSignal.emit('add', submission_data)

            createSuccessInfoBar(self, "Submitted", "Data submitted to MR Update Interface")

    def onClear(self):
        """Clear all data"""
        self.current_file_path = None
        self.current_template = None
        self.parse_results = {}
        self.currentFileLabel.setText("No file selected")
        self.resultsTable.clear()
        self.resultsTable.setRowCount(0)
        self.parseBtn.setEnabled(False)
        self.submitBtn.setEnabled(False)
        self.saveTemplateBtn.setEnabled(False)

    def onSaveTemplate(self):
        """Save current patterns as a new template"""
        # Get template name from user
        dialog = QDialog(self)
        dialog.setWindowTitle("Save Template")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        # Template name
        name_edit = QLineEdit(dialog)
        name_edit.setPlaceholderText("Enter template name")
        form.addRow("Template Name:", name_edit)

        # Template type
        type_combo = QComboBox(dialog)
        type_combo.addItems(["MR Template", "NZ Template"])
        form.addRow("Template Type:", type_combo)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec():
            template_name = name_edit.text()
            is_mr = type_combo.currentIndex() == 0

            if not template_name:
                createWarningInfoBar(self, "Invalid Name", "Please enter a template name")
                return

            # Get patterns from table
            patterns = self.resultsTable.getPatterns()

            # Save template
            if self.parser_service.save_template(template_name, patterns, is_mr):
                createSuccessInfoBar(self, "Template Saved", f"Template '{template_name}' saved successfully")
                self.loadTemplates()  # Reload templates
            else:
                createErrorInfoBar(self, "Failed to save template", title="Save Failed")

    def onBrowseFolder(self):
        """Browse for folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folderPathEdit.setText(folder)

    @asyncSlot()
    @raise_error_bar_in_class
    async def onBatchProcess(self):
        """Process all files in folder with Hi-Trust UR template"""
        folder_path = self.folderPathEdit.text()
        if not folder_path or not os.path.exists(folder_path):
            createWarningInfoBar(self, "Invalid Path", "Please enter a valid folder path")
            return

        try:
            self.batchProcessBtn.setEnabled(False)

            # Get all supported files in folder
            files = []
            for ext in ['*.pdf', '*.xlsx', '*.xls']:
                files.extend(Path(folder_path).glob(ext))

            if not files:
                createWarningInfoBar(self, "No Files", "No supported files found in folder")
                return

            # Process each file
            success_count = 0
            failed_files = []

            for file_path in files:
                try:
                    results = await self.parser_service.parse_file(
                        str(file_path),
                        'Hi-Trust UR'
                    )

                    if results:
                        # Extract header info from filename if possible
                        # Format: {Asset_ID}_{Client_ID}_{Ex_Date}_{ACT/EST}
                        filename = file_path.stem
                        parts = filename.split('_')

                        header_data = {
                            'asset_id': parts[0] if len(parts) > 0 else '',
                            'client_id': parts[1] if len(parts) > 1 else '',
                            'type': 'Last Actual'  # Hi-Trust UR uses ACT type
                        }

                        # Try to parse date from filename
                        if len(parts) > 2:
                            try:
                                ex_date = datetime.strptime(parts[2], '%d%b%Y').date()
                                header_data['ex_date'] = ex_date
                            except:
                                pass

                        # Auto-submit to MR Update
                        submission_data = {
                            'header': header_data,
                            'data': {k: v['value'] for k, v in results.items() if v['value']},
                            'source_file': str(file_path),
                            'template': 'Hi-Trust UR',
                            'timestamp': datetime.now()
                        }

                        signalBus.mrUpdateSignal.emit('add', submission_data)
                        success_count += 1

                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    failed_files.append(str(file_path.name))

            # Show results
            message = f"Processed {success_count}/{len(files)} files successfully"
            if failed_files:
                message += f"\n\nFailed files:\n" + "\n".join(failed_files[:5])
                if len(failed_files) > 5:
                    message += f"\n... and {len(failed_files) - 5} more"

            if success_count > 0:
                createSuccessInfoBar(self, "Batch Complete", message)
            else:
                createErrorInfoBar(self, message, title="Batch Failed")

        finally:
            self.batchProcessBtn.setEnabled(True)

    def onParseComplete(self, success: bool, data: dict):
        """Handle parse complete signal"""
        if success:
            logger.info("Parse completed successfully", data=data)