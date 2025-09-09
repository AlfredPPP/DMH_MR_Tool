# src/dmh_mr_tool/ui/views/mr_update_view.py
"""MR Update Interface for managing and submitting parsed business records to DMH"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QCheckBox, QMenu, QDialog, QTextEdit,
    QDialogButtonBox, QFormLayout, QLabel, QProgressBar
)
from PySide6.QtGui import QAction
from qfluentwidgets import (
    CardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, InfoBar, InfoBarPosition,
    FluentIcon as FIF, TableWidget, CheckBox
)
from qasync import asyncSlot

from ..views.base_view import BaseInterface, SeparatorWidget
from ui.utils.signal_bus import signalBus
from ui.utils.infobar import raise_error_bar_in_class, createWarningInfoBar, createSuccessInfoBar
from business.services.dmh_service import DMH
from business.services.spider_service import SpiderService
from config.settings import CONFIG

import structlog

logger = structlog.get_logger()


@dataclass
class MRRecord:
    """Data class for MR Update record"""
    client_id: str
    asx_code: str
    fund: str
    asset_id: str
    ex_date: date
    pay_date: date
    mr_income_rate: float
    type: str
    status: str = "Pending"
    data_payload: Dict = None
    source_file: str = None
    template: str = None

    def get_key(self) -> str:
        """Get unique key for this record"""
        return f"{self.client_id}_{self.asset_id}_{self.ex_date}_{self.pay_date}_{self.mr_income_rate}"


class MRUpdateTable(QTableWidget):
    """Custom table widget for MR Update records"""

    fetchRequested = Signal(int)  # row index
    parseRequested = Signal(int)  # row index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.records: List[MRRecord] = []
        self.setupUI()

    def setupUI(self):
        # Set headers
        headers = ["", "Client ID", "ASX Code", "Fund", "Asset ID",
                   "Ex Date", "Pay Date", "MR Income Rate", "Type", "Actions", "Status"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        # Configure table
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 30)  # Checkbox column

        for i in range(1, 9):
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)

    def addRecord(self, record: MRRecord):
        """Add or update a record in the table"""
        # Check if record already exists
        existing_row = self.findRecord(record.get_key())

        if existing_row >= 0:
            # Update existing record
            self.records[existing_row] = record
            self.updateRow(existing_row, record)
        else:
            # Add new record
            row = self.rowCount()
            self.insertRow(row)
            self.records.append(record)

            # Checkbox
            checkbox = QCheckBox()
            self.setCellWidget(row, 0, checkbox)

            # Data columns
            self.setItem(row, 1, QTableWidgetItem(record.client_id))
            self.setItem(row, 2, QTableWidgetItem(record.asx_code))
            self.setItem(row, 3, QTableWidgetItem(record.fund))
            self.setItem(row, 4, QTableWidgetItem(record.asset_id))
            self.setItem(row, 5, QTableWidgetItem(record.ex_date.strftime("%Y-%m-%d")))
            self.setItem(row, 6, QTableWidgetItem(record.pay_date.strftime("%Y-%m-%d")))
            self.setItem(row, 7, QTableWidgetItem(f"{record.mr_income_rate:.6f}"))
            self.setItem(row, 8, QTableWidgetItem(record.type))

            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(2)

            fetch_btn = QPushButton("Fetch")
            fetch_btn.clicked.connect(lambda checked, r=row: self.fetchRequested.emit(r))
            parse_btn = QPushButton("Parse")
            parse_btn.clicked.connect(lambda checked, r=row: self.parseRequested.emit(r))

            action_layout.addWidget(fetch_btn)
            action_layout.addWidget(parse_btn)

            self.setCellWidget(row, 9, action_widget)

            # Status
            self.setItem(row, 10, QTableWidgetItem(record.status))

    def updateRow(self, row: int, record: MRRecord):
        """Update an existing row with new record data"""
        self.records[row] = record
        self.item(row, 1).setText(record.client_id)
        self.item(row, 2).setText(record.asx_code)
        self.item(row, 3).setText(record.fund)
        self.item(row, 4).setText(record.asset_id)
        self.item(row, 5).setText(record.ex_date.strftime("%Y-%m-%d"))
        self.item(row, 6).setText(record.pay_date.strftime("%Y-%m-%d"))
        self.item(row, 7).setText(f"{record.mr_income_rate:.6f}")
        self.item(row, 8).setText(record.type)
        self.item(row, 10).setText(record.status)

    def findRecord(self, key: str) -> int:
        """Find record by key, return row index or -1 if not found"""
        for i, record in enumerate(self.records):
            if record.get_key() == key:
                return i
        return -1

    def getSelectedRecords(self) -> List[MRRecord]:
        """Get all selected records"""
        selected = []
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected.append(self.records[row])
        return selected

    def selectAll(self, checked: bool):
        """Select or deselect all rows"""
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(checked)

    def showContextMenu(self, pos):
        """Show context menu"""
        menu = QMenu(self)

        # Get clicked row
        item = self.itemAt(pos)
        if item:
            row = item.row()

            view_action = QAction("View Details", self)
            view_action.triggered.connect(lambda: self.viewDetails(row))
            menu.addAction(view_action)

            edit_action = QAction("Edit", self)
            edit_action.triggered.connect(lambda: self.parseRequested.emit(row))
            menu.addAction(edit_action)

            menu.addSeparator()

            delete_action = QAction("Delete", self)
            delete_action.triggered.connect(lambda: self.deleteRow(row))
            menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))

    def viewDetails(self, row: int):
        """View detailed data for a record"""
        if 0 <= row < len(self.records):
            record = self.records[row]
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Details - {record.asset_id}")
            dialog.setModal(True)
            dialog.setMinimumSize(600, 400)

            layout = QVBoxLayout(dialog)

            # Show all data in formatted JSON
            text_edit = QTextEdit(dialog)
            text_edit.setReadOnly(True)

            details = {
                "Header": {
                    "Client ID": record.client_id,
                    "Asset ID": record.asset_id,
                    "Ex Date": record.ex_date.strftime("%Y-%m-%d"),
                    "Pay Date": record.pay_date.strftime("%Y-%m-%d"),
                    "MR Income Rate": record.mr_income_rate,
                    "Type": record.type
                },
                "Data Payload": record.data_payload or {},
                "Source File": record.source_file or "N/A",
                "Template": record.template or "N/A"
            }

            text_edit.setText(json.dumps(details, indent=2, default=str))
            layout.addWidget(text_edit)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dialog)
            buttons.accepted.connect(dialog.accept)
            layout.addWidget(buttons)

            dialog.exec()

    def deleteRow(self, row: int):
        """Delete a row"""
        if 0 <= row < self.rowCount():
            self.removeRow(row)
            del self.records[row]

    def updateStatus(self, row: int, status: str):
        """Update status for a specific row"""
        if 0 <= row < self.rowCount():
            self.item(row, 10).setText(status)
            self.records[row].status = status

            # Change row color based on status
            if status == "Success":
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.lightGray)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            elif status == "Failed":
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.red)


class BulkImportDialog(QDialog):
    """Dialog for bulk data import"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Import Data")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)

        # Instructions
        instructions = BodyLabel(
            "Paste data in tab-separated format:\n"
            "Client_ID  ASX_Code  Fund  Asset_ID  Ex_Date  Pay_Date  MR_Income_Rate  Type"
        )
        layout.addWidget(instructions)

        # Text area
        self.textEdit = QTextEdit(self)
        self.textEdit.setPlaceholderText("Paste your data here...")
        layout.addWidget(self.textEdit)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getData(self) -> List[Dict]:
        """Parse pasted data into list of dictionaries"""
        text = self.textEdit.toPlainText()
        if not text:
            return []

        lines = text.strip().split('\n')
        data = []

        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 8:
                try:
                    data.append({
                        'client_id': parts[0].strip(),
                        'asx_code': parts[1].strip(),
                        'fund': parts[2].strip(),
                        'asset_id': parts[3].strip(),
                        'ex_date': datetime.strptime(parts[4].strip(), "%Y%m%d").date(),
                        'pay_date': datetime.strptime(parts[5].strip(), "%Y%m%d").date(),
                        'mr_income_rate': float(parts[6].strip()),
                        'type': parts[7].strip() if len(parts) > 7 else 'Other'
                    })
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse line: {line}, error: {e}")

        return data


class MrUpdateInterface(BaseInterface):
    """MR Update Interface for managing parsed business records"""

    def __init__(self, parent=None):
        super().__init__(
            title="MR Update",
            subtitle="Manage and submit parsed business records to DMH system",
            parent=parent
        )
        self.setObjectName('mrUpdateInterface')
        self.dmh_service = DMH()
        self.spider_service = SpiderService()
        self.initUI()
        self.connectSignalToSlot()

    def initUI(self):
        """Initialize the user interface"""
        self.body_layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(self.body_layout)

        # Control buttons
        self.addControlButtons()

        # Main table
        self.addMainTable()

        # Status bar
        self.addStatusBar()

        self.addPageBody("", widget, stretch=1)

    def addControlButtons(self):
        """Add control buttons section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # Select all checkbox
        self.selectAllCheck = CheckBox("Select All", widget)
        self.selectAllCheck.toggled.connect(self.onSelectAll)

        # Submit button
        self.submitBtn = PrimaryPushButton("Submit Selected", widget)
        self.submitBtn.setIcon(FIF.SEND)
        self.submitBtn.clicked.connect(self.onSubmit)

        # Delete button
        self.deleteBtn = PushButton("Delete Selected", widget)
        self.deleteBtn.setIcon(FIF.DELETE)
        self.deleteBtn.clicked.connect(self.onDelete)

        # Bulk import button
        self.bulkImportBtn = PushButton("Bulk Import", widget)
        self.bulkImportBtn.setIcon(FIF.PASTE)
        self.bulkImportBtn.clicked.connect(self.onBulkImport)

        # Refresh button
        self.refreshBtn = PushButton("Refresh", widget)
        self.refreshBtn.setIcon(FIF.SYNC)
        self.refreshBtn.clicked.connect(self.onRefresh)

        layout.addWidget(self.selectAllCheck)
        layout.addWidget(self.submitBtn)
        layout.addWidget(self.deleteBtn)
        layout.addWidget(self.bulkImportBtn)
        layout.addWidget(self.refreshBtn)
        layout.addStretch()

        title = StrongBodyLabel("Actions")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addMainTable(self):
        """Add main records table"""
        self.recordsTable = MRUpdateTable(self)
        self.recordsTable.setMinimumHeight(400)
        self.recordsTable.fetchRequested.connect(self.onFetchRecord)
        self.recordsTable.parseRequested.connect(self.onParseRecord)

        title = StrongBodyLabel("Business Records")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(self.recordsTable)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addStatusBar(self):
        """Add status bar section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Progress bar
        self.progressBar = QProgressBar(widget)
        self.progressBar.setVisible(False)
        self.progressBar.setMaximumWidth(200)

        # Status label
        self.statusLabel = CaptionLabel("Ready", widget)

        # Statistics
        self.statsLabel = CaptionLabel("Total: 0 | Pending: 0 | Success: 0 | Failed: 0", widget)

        layout.addWidget(self.statusLabel)
        layout.addWidget(self.progressBar)
        layout.addStretch()
        layout.addWidget(self.statsLabel)

        self.body_layout.addWidget(widget)

    def connectSignalToSlot(self):
        """Connect signals to slots"""
        # Connect to MR Update signal from signal bus
        if hasattr(signalBus, 'mrUpdateSignal'):
            signalBus.mrUpdateSignal.connect(self.onMRUpdateSignal)

        # Connect to parser interface if available
        parent = self.parent()
        while parent:
            if hasattr(parent, 'parserInterface'):
                parent.parserInterface.dataSubmitted.connect(self.onDataFromParser)
                break
            parent = parent.parent()

    def onMRUpdateSignal(self, action: str, data: dict):
        """Handle MR Update signal from signal bus"""
        if action == 'add':
            self.addRecordFromData(data)
        elif action == 'update':
            # Update existing record
            pass
        elif action == 'delete':
            # Delete record
            pass

    def onDataFromParser(self, data: dict):
        """Handle data from Parser Interface"""
        self.addRecordFromData(data)

    def addRecordFromData(self, data: dict):
        """Add record from parsed data"""
        header = data.get('header', {})
        payload = data.get('data', {})

        # Create MRRecord
        record = MRRecord(
            client_id=header.get('client_id', ''),
            asx_code=header.get('asx_code', ''),
            fund=header.get('fund', ''),
            asset_id=header.get('asset_id', ''),
            ex_date=header.get('ex_date', datetime.now().date()),
            pay_date=header.get('pay_date', datetime.now().date()),
            mr_income_rate=header.get('mr_income_rate', 0.0),
            type=header.get('type', 'Other'),
            data_payload=payload,
            source_file=data.get('source_file'),
            template=data.get('template')
        )

        self.recordsTable.addRecord(record)
        self.updateStatistics()

    def onSelectAll(self, checked: bool):
        """Handle select all checkbox"""
        self.recordsTable.selectAll(checked)

    @asyncSlot()
    @raise_error_bar_in_class
    async def onSubmit(self):
        """Submit selected records to DMH"""
        selected = self.recordsTable.getSelectedRecords()
        if not selected:
            createWarningInfoBar(self, "No Selection", "Please select records to submit")
            return

        try:
            self.submitBtn.setEnabled(False)
            self.progressBar.setVisible(True)
            self.progressBar.setMaximum(len(selected))

            success_count = 0
            failed_count = 0

            for i, record in enumerate(selected):
                self.progressBar.setValue(i)
                self.statusLabel.setText(f"Submitting {record.asset_id}...")

                try:
                    # Find the row for this record
                    row = self.recordsTable.findRecord(record.get_key())
                    self.recordsTable.updateStatus(row, "Submitting...")

                    # Submit to DMH
                    result = await self.dmh_service.submit_mr_data(record)

                    if result['success']:
                        self.recordsTable.updateStatus(row, "Success")
                        success_count += 1

                        # Save backup file
                        self.saveBackupFile(record)
                    else:
                        self.recordsTable.updateStatus(row, f"Failed: {result.get('error', 'Unknown')}")
                        failed_count += 1

                except Exception as e:
                    logger.error(f"Failed to submit record: {e}")
                    self.recordsTable.updateStatus(row, f"Failed: {str(e)}")
                    failed_count += 1

            self.progressBar.setValue(len(selected))
            self.statusLabel.setText("Submission complete")

            createSuccessInfoBar(
                self,
                "Submission Complete",
                f"Success: {success_count}, Failed: {failed_count}"
            )

        finally:
            self.submitBtn.setEnabled(True)
            self.progressBar.setVisible(False)
            self.updateStatistics()

    def onDelete(self):
        """Delete selected records"""
        selected = self.recordsTable.getSelectedRecords()
        if not selected:
            createWarningInfoBar(self, "No Selection", "Please select records to delete")
            return

        # Delete from bottom to top to maintain row indices
        for record in reversed(selected):
            row = self.recordsTable.findRecord(record.get_key())
            if row >= 0:
                self.recordsTable.deleteRow(row)

        self.updateStatistics()
        createSuccessInfoBar(self, "Deleted", f"Deleted {len(selected)} records")

    def onBulkImport(self):
        """Handle bulk import"""
        dialog = BulkImportDialog(self)
        if dialog.exec():
            data_list = dialog.getData()
            for data in data_list:
                record = MRRecord(**data)
                self.recordsTable.addRecord(record)

            self.updateStatistics()
            createSuccessInfoBar(self, "Import Complete", f"Imported {len(data_list)} records")

    def onRefresh(self):
        """Refresh table display"""
        self.updateStatistics()

    @asyncSlot()
    @raise_error_bar_in_class
    async def onFetchRecord(self, row: int):
        """Fetch PDF for a record"""
        if 0 <= row < len(self.recordsTable.records):
            record = self.recordsTable.records[row]

            try:
                self.recordsTable.updateStatus(row, "Fetching...")

                # Search for announcement in database
                announcements = self.spider_service.get_announcements_by_criteria(
                    asx_code=record.asx_code,
                    start_date=record.ex_date,
                    end_date=record.pay_date
                )

                if announcements:
                    # Download PDF
                    pdf_path = CONFIG.paths.download_path / f"{record.asset_id}_{record.ex_date}.pdf"
                    success = await self.spider_service.download_pdf(
                        announcements[0].id,
                        str(pdf_path)
                    )

                    if success:
                        self.recordsTable.updateStatus(row, "Pending parse")
                        record.source_file = str(pdf_path)
                        createSuccessInfoBar(self, "Fetched", "PDF downloaded successfully")
                    else:
                        self.recordsTable.updateStatus(row, "Fetch failed")
                else:
                    self.recordsTable.updateStatus(row, "Not found")
                    createWarningInfoBar(self, "Not Found", "No matching announcement found")

            except Exception as e:
                logger.error(f"Fetch error: {e}")
                self.recordsTable.updateStatus(row, "Error")
                raise

    def onParseRecord(self, row: int):
        """Open parser interface for a record"""
        if 0 <= row < len(self.recordsTable.records):
            record = self.recordsTable.records[row]

            # Navigate to parser interface with this record's data
            parent = self.parent()
            while parent:
                if hasattr(parent, 'parserInterface'):
                    # Load file if available
                    if record.source_file and os.path.exists(record.source_file):
                        parent.parserInterface.onFileSelected(record.source_file)

                    # Switch to parser tab
                    if hasattr(parent, 'stackedWidget'):
                        parent.stackedWidget.setCurrentWidget(parent.parserInterface)

                    break
                parent = parent.parent()

    def saveBackupFile(self, record: MRRecord):
        """Save backup file after successful submission"""
        if record.source_file and os.path.exists(record.source_file):
            # Generate backup filename
            template_type = "ACT" if record.template == "Hi-Trust UR" else "EST"
            backup_name = f"{record.asset_id}_{record.client_id}_{record.ex_date.strftime('%d%b%Y')}_{template_type}"
            backup_path = CONFIG.paths.backup_path / backup_name

            # Copy file to back-up location
            import shutil
            shutil.copy2(record.source_file, backup_path)
            logger.info(f"Backup saved: {backup_path}")

    def updateStatistics(self):
        """Update statistics display"""
        total = len(self.recordsTable.records)
        pending = sum(1 for r in self.recordsTable.records if r.status == "Pending")
        success = sum(1 for r in self.recordsTable.records if r.status == "Success")
        failed = sum(1 for r in self.recordsTable.records if "Failed" in r.status)

        self.statsLabel.setText(f"Total: {total} | Pending: {pending} | Success: {success} | Failed: {failed}")