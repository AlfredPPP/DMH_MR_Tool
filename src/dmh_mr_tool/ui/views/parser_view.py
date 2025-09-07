# src/dmh_mr_tool/ui/views/parser_view.py
"""Parser interface for file parsing and template-based data extraction"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QFileDialog, QMessageBox,
    QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QMimeData, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
import structlog

from qfluentwidgets import (
    PrimaryPushButton, PushButton, BodyLabel, StrongBodyLabel,
    LineEdit, ComboBox, TableWidget, TextEdit, CardWidget,
    FluentIcon as FIF, InfoBarPosition, GroupHeaderCardWidget
)

from ui.views.base_view import BaseInterface
from ui.utils.signal_bus import signalBus
from ui.utils.infobar import raise_error_bar_in_class
from business.services.parser_service import ParseService
from database.connection import DatabaseManager, DatabaseConfig
from database.repositories.asx_repository import AsxInfoRepository
from database.models import ParseTemplateMR, ParseTemplateNZ
from config.settings import CONFIG

logger = structlog.get_logger()


class DropZoneWidget(QWidget):
    """Drag and drop zone for file uploads"""

    fileDropped = Signal(str)  # Signal emitted when file is dropped

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setStyleSheet("""
            DropZoneWidget {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f9f9f9;
                color: #666;
            }
            DropZoneWidget:hover {
                border-color: #0078d4;
                background-color: #f0f8ff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.label = BodyLabel("Drag and drop PDF/Excel files here\nor click to browse")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.browse_btn = PushButton("Browse Files")
        self.browse_btn.clicked.connect(self._browse_files)
        layout.addWidget(self.browse_btn)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(('.pdf', '.xlsx', '.xls')) for url in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        valid_files = [f for f in files if f.lower().endswith(('.pdf', '.xlsx', '.xls'))]

        if valid_files:
            # For now, take the first valid file
            self.fileDropped.emit(valid_files[0])
            event.acceptProposedAction()
        else:
            event.ignore()

    def _browse_files(self):
        """Open file browser"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Parse",
            "",
            "Supported Files (*.pdf *.xlsx *.xls);;PDF Files (*.pdf);;Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.fileDropped.emit(file_path)


class ParseResultTableWidget(TableWidget):
    """Custom table widget for displaying parse results"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Column Name", "Regex Pattern", "Parsed Value", "Comment"])

        # Set column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)


class ParserInterface(BaseInterface):
    """Parser interface for file parsing and template-based data extraction"""

    def __init__(self, parent=None):
        super().__init__(
            title="Parser - File Data Extraction",
            subtitle="Extract data from PDF and Excel files using templates",
            parent=parent
        )
        self.setObjectName('parserInterface')
        self.parent_window = parent
        self.db_manager: Optional[DatabaseManager] = None
        self.parser_service: Optional[ParseService] = None
        self.current_file_path: Optional[str] = None
        self.current_template: Optional[str] = None
        self.current_parsed_data: Dict[str, Any] = {}
        self.templates_data: Dict[str, Dict] = {}

        self._init_services()
        self._setup_ui()
        self._load_templates()
        self._connect_signals()

    def _init_services(self):
        """Initialize database manager and parser service"""
        try:
            self.db_manager = DatabaseManager(DatabaseConfig(path=CONFIG.database.path))
            self.db_manager.initialize()
            self.parser_service = ParseService()
            logger.info("Parser services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize parser services: {e}")
            signalBus.infoBarSignal.emit("ERROR", "Initialization Error",
                                         f"Failed to initialize parser services: {str(e)}")

    def _setup_ui(self):
        """Set up the parser interface"""
        # File Input Section
        self._create_file_input_section()

        # Template Selection Section
        self._create_template_section()

        # Parse Results Section
        self._create_results_section()

        # Action Buttons Section
        self._create_action_section()

    def _create_file_input_section(self):
        """Create file input section with drag-drop and folder path"""
        input_widget = QWidget()
        layout = QVBoxLayout(input_widget)

        # Drop zone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.fileDropped.connect(self._on_file_dropped)
        layout.addWidget(self.drop_zone)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Folder path input
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(BodyLabel("Folder Path:"))

        self.folder_path_input = LineEdit()
        self.folder_path_input.setPlaceholderText("Enter folder path to parse all files...")
        folder_layout.addWidget(self.folder_path_input)

        self.browse_folder_btn = PushButton(FIF.FOLDER, "Browse")
        self.browse_folder_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self.browse_folder_btn)

        self.parse_folder_btn = PrimaryPushButton("Parse Folder")
        self.parse_folder_btn.clicked.connect(self._parse_folder)
        folder_layout.addWidget(self.parse_folder_btn)

        layout.addLayout(folder_layout)

        # Current file info
        self.file_info_label = BodyLabel("No file selected")
        self.file_info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.file_info_label)

        self.addPageBody("File Input", input_widget)

    def _create_template_section(self):
        """Create template selection section"""
        template_widget = QWidget()
        layout = QHBoxLayout(template_widget)

        # Template selection
        layout.addWidget(BodyLabel("Template:"))

        self.template_combo = ComboBox()
        self.template_combo.setMinimumWidth(200)
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        layout.addWidget(self.template_combo)

        # Parse button
        self.parse_btn = PrimaryPushButton(FIF.SYNC, "Parse File")
        self.parse_btn.clicked.connect(self._parse_current_file)
        self.parse_btn.setEnabled(False)
        layout.addWidget(self.parse_btn)

        layout.addStretch()

        # Template info
        self.template_info_label = BodyLabel("Select a template to see details")
        self.template_info_label.setStyleSheet("color: #666;")
        layout.addWidget(self.template_info_label)

        self.addPageBody("Template Selection", template_widget)

    def _create_results_section(self):
        """Create parse results section"""
        results_widget = QWidget()
        layout = QVBoxLayout(results_widget)

        # Results table
        self.results_table = ParseResultTableWidget()
        layout.addWidget(self.results_table)

        # Add extra row section
        extra_row_layout = QHBoxLayout()
        extra_row_layout.addWidget(BodyLabel("Add Extra Row:"))

        self.extra_column_combo = ComboBox()
        self.extra_column_combo.setMinimumWidth(150)
        extra_row_layout.addWidget(self.extra_column_combo)

        self.extra_value_input = LineEdit()
        self.extra_value_input.setPlaceholderText("Enter value...")
        extra_row_layout.addWidget(self.extra_value_input)

        self.extra_comment_input = LineEdit()
        self.extra_comment_input.setPlaceholderText("Enter comment...")
        extra_row_layout.addWidget(self.extra_comment_input)

        self.add_row_btn = PushButton(FIF.ADD, "Add Row")
        self.add_row_btn.clicked.connect(self._add_extra_row)
        extra_row_layout.addWidget(self.add_row_btn)

        layout.addLayout(extra_row_layout)

        self.addPageBody("Parse Results", results_widget)

    def _create_action_section(self):
        """Create action buttons section"""
        action_widget = QWidget()
        layout = QHBoxLayout(action_widget)

        # Submit to MR Update button
        self.submit_btn = PrimaryPushButton(FIF.SEND, "Submit to MR Update")
        self.submit_btn.clicked.connect(self._submit_to_mr_update)
        self.submit_btn.setEnabled(False)
        layout.addWidget(self.submit_btn)

        # Clear results button
        self.clear_btn = PushButton(FIF.DELETE, "Clear Results")
        self.clear_btn.clicked.connect(self._clear_results)
        layout.addWidget(self.clear_btn)

        layout.addStretch()

        # Status label
        self.status_label = BodyLabel("Ready")
        layout.addWidget(self.status_label)

        self.addPageBody("Actions", action_widget)

    def _load_templates(self):
        """Load templates from database"""
        try:
            if not self.db_manager:
                return

            with self.db_manager.session() as session:
                # Load MR templates
                mr_templates = session.query(ParseTemplateMR).filter_by(is_valid=True).all()
                for template in mr_templates:
                    template_data = {
                        'type': 'mr',
                        'columns': {}
                    }
                    # Get all columns except metadata columns
                    for column in template.__table__.columns:
                        if column.name not in ['id', 'template_name', 'is_valid', 'update_timestamp']:
                            value = getattr(template, column.name)
                            if value:
                                template_data['columns'][column.name] = value

                    self.templates_data[f"{template.template_name} (MR)"] = template_data

                # Load NZ templates
                nz_templates = session.query(ParseTemplateNZ).filter_by(is_valid=True).all()
                for template in nz_templates:
                    template_data = {
                        'type': 'nz',
                        'columns': {}
                    }
                    # Get all columns except metadata columns
                    for column in template.__table__.columns:
                        if column.name not in ['id', 'template_name', 'is_valid', 'update_timestamp']:
                            value = getattr(template, column.name)
                            if value:
                                template_data['columns'][column.name] = value

                    self.templates_data[f"{template.template_name} (NZ)"] = template_data

            # Populate template combo
            self.template_combo.clear()
            self.template_combo.addItems(list(self.templates_data.keys()))

            # Populate extra column combo (all possible columns)
            all_columns = set()
            for template_data in self.templates_data.values():
                all_columns.update(template_data['columns'].keys())

            self.extra_column_combo.clear()
            self.extra_column_combo.addItems(sorted(all_columns))

            logger.info(f"Loaded {len(self.templates_data)} templates")

        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            signalBus.infoBarSignal.emit("ERROR", "Template Load Error",
                                         f"Failed to load templates: {str(e)}")

    def _connect_signals(self):
        """Connect signals"""
        # Results table value changes
        self.results_table.itemChanged.connect(self._on_result_value_changed)

    @raise_error_bar_in_class
    def _on_file_dropped(self, file_path: str):
        """Handle file drop event"""
        self.current_file_path = file_path
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / 1024  # KB

        self.file_info_label.setText(f"Selected: {file_name} ({file_size:.1f} KB)")
        self.parse_btn.setEnabled(True)
        self.status_label.setText("File ready for parsing")

        signalBus.infoBarSignal.emit("SUCCESS", "File Selected",
                                     f"File {file_name} ready for parsing")

    @raise_error_bar_in_class
    def _browse_folder(self):
        """Browse for folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder Containing Files to Parse"
        )
        if folder_path:
            self.folder_path_input.setText(folder_path)

    @raise_error_bar_in_class
    def _on_template_changed(self, template_name: str):
        """Handle template selection change"""
        if not template_name or template_name not in self.templates_data:
            self.template_info_label.setText("Select a template to see details")
            self.current_template = None
            return

        self.current_template = template_name
        template_data = self.templates_data[template_name]
        column_count = len(template_data['columns'])
        template_type = template_data['type'].upper()

        self.template_info_label.setText(
            f"Template: {template_name} | Type: {template_type} | Columns: {column_count}"
        )

    @raise_error_bar_in_class
    def _parse_current_file(self):
        """Parse the currently selected file"""
        if not self.current_file_path or not self.current_template:
            signalBus.infoBarSignal.emit("WARNING", "Parse Error",
                                         "Please select both file and template")
            return

        asyncio.create_task(self._parse_file_async(self.current_file_path, self.current_template))

    @raise_error_bar_in_class
    async def _parse_file_async(self, file_path: str, template_name: str):
        """Parse file asynchronously"""
        try:
            self.status_label.setText("Parsing file...")
            self.parse_btn.setEnabled(False)

            # Get template data
            template_data = self.templates_data[template_name]

            # Read file content
            file_content = ""
            if file_path.lower().endswith('.pdf'):
                # Use parser service to extract PDF content
                file_content = await self.parser_service.extract_pdf_content(file_path)
            elif file_path.lower().endswith(('.xlsx', '.xls')):
                # Use parser service to extract Excel content
                file_content = await self.parser_service.extract_excel_content(file_path)
            else:
                raise ValueError("Unsupported file format")

            # Parse using regex patterns
            parsed_data = {}
            for column_name, regex_pattern in template_data['columns'].items():
                if regex_pattern:
                    match = re.search(regex_pattern, file_content, re.MULTILINE | re.DOTALL)
                    if match:
                        parsed_data[column_name] = match.group(1) if match.groups() else match.group(0)
                    else:
                        parsed_data[column_name] = ""
                else:
                    parsed_data[column_name] = ""

            # Apply business rules for calculated fields
            parsed_data = self._apply_business_rules(parsed_data, template_data['type'])

            # Store current parsed data
            self.current_parsed_data = parsed_data

            # Display results
            self._display_parse_results(template_data, parsed_data)

            self.status_label.setText("Parsing completed successfully")
            self.submit_btn.setEnabled(True)

            signalBus.infoBarSignal.emit("SUCCESS", "Parse Complete",
                                         f"Successfully parsed {len(parsed_data)} fields")

        except Exception as e:
            logger.error(f"Parse failed: {e}")
            self.status_label.setText("Parse failed")
            signalBus.infoBarSignal.emit("ERROR", "Parse Error", f"Failed to parse file: {str(e)}")
        finally:
            self.parse_btn.setEnabled(True)

    def _apply_business_rules(self, parsed_data: Dict[str, Any], template_type: str) -> Dict[str, Any]:
        """Apply business rules to parsed data"""
        # Example business rules - customize based on your requirements
        if template_type == 'nz':
            # Example: tax_rate default value
            if not parsed_data.get('tax_rate'):
                parsed_data['tax_rate'] = '0.3'  # Default value per client specific

            # Example: total = sum of other components (if applicable)
            # This would be more complex in real implementation

        elif template_type == 'mr':
            # Add MR-specific business rules here
            pass

        return parsed_data

    def _display_parse_results(self, template_data: Dict, parsed_data: Dict[str, Any]):
        """Display parse results in the table"""
        self.results_table.setRowCount(0)

        row = 0
        for column_name, regex_pattern in template_data['columns'].items():
            self.results_table.insertRow(row)

            # Column name
            self.results_table.setItem(row, 0, QTableWidgetItem(column_name))

            # Regex pattern
            pattern_item = QTableWidgetItem(regex_pattern or "")
            pattern_item.setFlags(pattern_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 1, pattern_item)

            # Parsed value (editable)
            value = parsed_data.get(column_name, "")
            value_item = QTableWidgetItem(str(value))
            self.results_table.setItem(row, 2, value_item)

            # Comment
            comment = ""
            if not regex_pattern:
                comment = "Default value per client specific"
            elif not value:
                comment = "No match found"

            comment_item = QTableWidgetItem(comment)
            comment_item.setFlags(comment_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 3, comment_item)

            row += 1

    @raise_error_bar_in_class
    def _add_extra_row(self):
        """Add extra row to results table"""
        column_name = self.extra_column_combo.currentText()
        value = self.extra_value_input.text().strip()
        comment = self.extra_comment_input.text().strip()

        if not column_name or not value:
            signalBus.infoBarSignal.emit("WARNING", "Input Error",
                                         "Please enter both column name and value")
            return

        # Check if column already exists
        for row in range(self.results_table.rowCount()):
            if self.results_table.item(row, 0).text() == column_name:
                signalBus.infoBarSignal.emit("WARNING", "Duplicate Column",
                                             f"Column {column_name} already exists")
                return

        # Add new row
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        self.results_table.setItem(row, 0, QTableWidgetItem(column_name))

        pattern_item = QTableWidgetItem("Manual Entry")
        pattern_item.setFlags(pattern_item.flags() & ~Qt.ItemIsEditable)
        self.results_table.setItem(row, 1, pattern_item)

        self.results_table.setItem(row, 2, QTableWidgetItem(value))

        comment_item = QTableWidgetItem(comment or "Manually added")
        comment_item.setFlags(comment_item.flags() & ~Qt.ItemIsEditable)
        self.results_table.setItem(row, 3, comment_item)

        # Clear inputs
        self.extra_value_input.clear()
        self.extra_comment_input.clear()

        # Update current parsed data
        self.current_parsed_data[column_name] = value

    def _on_result_value_changed(self, item):
        """Handle changes to result values"""
        if item.column() == 2:  # Value column
            row = item.row()
            column_name = self.results_table.item(row, 0).text()
            new_value = item.text()

            # Update current parsed data
            self.current_parsed_data[column_name] = new_value

    @raise_error_bar_in_class
    def _submit_to_mr_update(self):
        """Submit parsed data to MR Update Interface"""
        if not self.current_parsed_data:
            signalBus.infoBarSignal.emit("WARNING", "No Data",
                                         "No parsed data to submit")
            return

        # Show input dialog for additional required information
        dialog = MRSubmissionDialog(self)
        if dialog.exec_() == QMessageBox.Accepted:
            additional_data = dialog.get_data()

            # Combine parsed data with additional data
            submission_data = {
                **self.current_parsed_data,
                **additional_data,
                'source_file': self.current_file_path,
                'template_used': self.current_template,
                'parse_timestamp': datetime.now().isoformat()
            }

            # Send to MR Update Interface via signal or direct method call
            if hasattr(self.parent_window, 'mrUpdateInterface'):
                self.parent_window.mrUpdateInterface.receive_parsed_data(submission_data)

            signalBus.infoBarSignal.emit("SUCCESS", "Data Submitted",
                                         "Parsed data submitted to MR Update Interface")

            # Switch to MR Update tab
            self.parent_window.switchTo(self.parent_window.mrUpdateInterface)

    @raise_error_bar_in_class
    def _parse_folder(self):
        """Parse all files in the selected folder"""
        folder_path = self.folder_path_input.text().strip()
        if not folder_path or not os.path.exists(folder_path):
            signalBus.infoBarSignal.emit("WARNING", "Invalid Path",
                                         "Please enter a valid folder path")
            return

        asyncio.create_task(self._parse_folder_async(folder_path))

    async def _parse_folder_async(self, folder_path: str):
        """Parse all files in folder asynchronously"""
        try:
            self.status_label.setText("Parsing folder...")

            # Find all supported files
            supported_extensions = ('.pdf', '.xlsx', '.xls')
            files = []
            for ext in supported_extensions:
                files.extend(Path(folder_path).glob(f"*{ext}"))

            if not files:
                signalBus.infoBarSignal.emit("WARNING", "No Files Found",
                                             "No supported files found in the folder")
                return

            if not self.current_template:
                signalBus.infoBarSignal.emit("WARNING", "No Template",
                                             "Please select a template first")
                return

            # Parse each file and collect results
            all_results = []
            for file_path in files:
                try:
                    template_data = self.templates_data[self.current_template]

                    # Read file content
                    if str(file_path).lower().endswith('.pdf'):
                        file_content = await self.parser_service.extract_pdf_content(str(file_path))
                    else:
                        file_content = await self.parser_service.extract_excel_content(str(file_path))

                    # Parse using regex patterns
                    parsed_data = {}
                    for column_name, regex_pattern in template_data['columns'].items():
                        if regex_pattern:
                            match = re.search(regex_pattern, file_content, re.MULTILINE | re.DOTALL)
                            if match:
                                parsed_data[column_name] = match.group(1) if match.groups() else match.group(0)
                            else:
                                parsed_data[column_name] = ""
                        else:
                            parsed_data[column_name] = ""

                    # Apply business rules
                    parsed_data = self._apply_business_rules(parsed_data, template_data['type'])

                    # Add file info
                    parsed_data['source_file'] = str(file_path)
                    parsed_data['template_used'] = self.current_template

                    all_results.append(parsed_data)

                except Exception as e:
                    logger.error(f"Failed to parse {file_path}: {e}")

            # Send all results to MR Update Interface
            if all_results and hasattr(self.parent_window, 'mrUpdateInterface'):
                self.parent_window.mrUpdateInterface.receive_bulk_parsed_data(all_results)

                signalBus.infoBarSignal.emit("SUCCESS", "Folder Parsed",
                                             f"Parsed {len(all_results)} files successfully")

                # Switch to MR Update tab
                self.parent_window.switchTo(self.parent_window.mrUpdateInterface)
            else:
                signalBus.infoBarSignal.emit("WARNING", "No Results",
                                             "No files were successfully parsed")

        except Exception as e:
            logger.error(f"Folder parse failed: {e}")
            signalBus.infoBarSignal.emit("ERROR", "Parse Error",
                                         f"Failed to parse folder: {str(e)}")
        finally:
            self.status_label.setText("Ready")

    def _clear_results(self):
        """Clear all results"""
        self.results_table.setRowCount(0)
        self.current_parsed_data.clear()
        self.submit_btn.setEnabled(False)
        self.status_label.setText("Results cleared")
        signalBus.infoBarSignal.emit("SUCCESS", "Cleared", "Parse results cleared")

    def refresh(self):
        """Refresh the view"""
        self._load_templates()
        self._clear_results()


class MRSubmissionDialog(QMessageBox):
    """Dialog for collecting additional MR submission data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Submit to MR Update")
        self.setText("Please provide additional information for MR submission:")
        self.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        # Create input fields
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Asset ID
        layout.addWidget(QLabel("Asset ID:"))
        self.asset_id_input = QLineEdit()
        self.asset_id_input.setPlaceholderText("Enter Asset ID...")
        layout.addWidget(self.asset_id_input)

        # Ex Date
        layout.addWidget(QLabel("Ex Date:"))
        self.ex_date_input = QLineEdit()
        self.ex_date_input.setPlaceholderText("YYYY-MM-DD")
        layout.addWidget(self.ex_date_input)

        # Pay Date
        layout.addWidget(QLabel("Pay Date:"))
        self.pay_date_input = QLineEdit()
        self.pay_date_input.setPlaceholderText("YYYY-MM-DD")
        layout.addWidget(self.pay_date_input)

        # MR Income Rate
        layout.addWidget(QLabel("MR Income Rate:"))
        self.income_rate_input = QLineEdit()
        self.income_rate_input.setPlaceholderText("Enter income rate...")
        layout.addWidget(self.income_rate_input)

        # Add the widget to the message box
        self.layout().addWidget(widget, 1, 1)

    def get_data(self) -> Dict[str, str]:
        """Get the input data"""
        return {
            'asset_id': self.asset_id_input.text().strip(),
            'ex_date': self.ex_date_input.text().strip(),
            'pay_date': self.pay_date_input.text().strip(),
            'mr_income_rate': self.income_rate_input.text().strip()
        }