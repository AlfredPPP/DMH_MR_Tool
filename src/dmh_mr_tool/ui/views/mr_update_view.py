# src/dmh_mr_tool/ui/views/mr_update_view.py
"""MR Update interface for managing and submitting tasks to DMH system"""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QFileDialog, QMessageBox,
    QFrame, QSpacerItem, QSizePolicy, QAbstractItemView,
    QMenu, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QAction, QColor
import structlog

from qfluentwidgets import (
    PrimaryPushButton, PushButton, BodyLabel, StrongBodyLabel,
    LineEdit, ComboBox, TableWidget, TextEdit, CardWidget,
    FluentIcon as FIF, InfoBarPosition, ProgressBar, StateToolTip
)

from ui.views.base_view import BaseInterface
from ui.utils.signal_bus import signalBus
from ui.utils.infobar import raise_error_bar_in_class
from business.services.dmh_service import DMH
from database.connection import DatabaseManager, DatabaseConfig
from database.models import SystemLog
from core.utils import USERNAME
from config.settings import CONFIG

logger = structlog.get_logger()


class MRTaskTableWidget(TableWidget):
    """Custom table widget for MR tasks with context menu and status updates"""

    parseRequested = Signal(dict)  # Signal for parse button clicks

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(9)
        self.setHorizontalHeaderLabels([
            "Client_ID", "Fund", "Asset_ID", "Ex_Date", "Pay_Date",
            "MR_Income", "Type", "Action", "Status"
        ])

        # Set column properties
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Client_ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Fund
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Asset_ID
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Ex_Date
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Pay_Date
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # MR_Income
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Type
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Action
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # Status

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Store task data
        self.task_data: List[Dict] = []

    def add_task(self, task_data: Dict):
        """Add a new task to the table"""
        row = self.rowCount()
        self.insertRow(row)

        # Store task data
        self.task_data.append(task_data)

        # Populate row
        self._populate_row(row, task_data)

    def add_bulk_tasks(self, tasks_data: List[Dict]):
        """Add multiple tasks to the table"""
        for task_data in tasks_data:
            self.add_task(task_data)

    def _populate_row(self, row: int, task_data: Dict):
        """Populate a table row with task data"""
        # Basic task information
        self.setItem(row, 0, QTableWidgetItem(task_data.get('client_id', '')))
        self.setItem(row, 1, QTableWidgetItem(task_data.get('fund', '')))
        self.setItem(row, 2, QTableWidgetItem(task_data.get('asset_id', '')))
        self.setItem(row, 3, QTableWidgetItem(task_data.get('ex_date', '')))
        self.setItem(row, 4, QTableWidgetItem(task_data.get('pay_date', '')))
        self.setItem(row, 5, QTableWidgetItem(str(task_data.get('mr_income', ''))))
        self.setItem(row, 6, QTableWidgetItem(task_data.get('type', 'Other')))

        # Action buttons widget
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(2, 2, 2, 2)

        fetch_btn = PushButton("Fetch")
        fetch_btn.setMaximumSize(60, 25)
        fetch_btn.clicked.connect(lambda: self._on_fetch_clicked(row))
        action_layout.addWidget(fetch_btn)

        parse_btn = PushButton("Parse")
        parse_btn.setMaximumSize(60, 25)
        parse_btn.clicked.connect(lambda: self._on_parse_clicked(row))
        action_layout.addWidget(parse_btn)

        self.setCellWidget(row, 7, action_widget)

        # Status
        status_item = QTableWidgetItem(task_data.get('status', 'Pending'))
        self._update_status_color(status_item, task_data.get('status', 'Pending'))
        self.setItem(row, 8, status_item)

    def _update_status_color(self, item: QTableWidgetItem, status: str):
        """Update status item color based on status"""
        if status.lower() == 'success':
            item.setBackground(QColor(200, 255, 200))  # Light green
        elif status.lower() == 'failed':
            item.setBackground(QColor(255, 200, 200))  # Light red
        elif status.lower() == 'processing':
            item.setBackground(QColor(255, 255, 200))  # Light yellow
        else:
            item.setBackground(QColor(240, 240, 240))  # Light gray

    def _on_fetch_clicked(self, row: int):
        """Handle fetch button click"""
        task_data = self.task_data[row] if row < len(self.task_data) else {}
        # Implement fetch logic here
        signalBus.infoBarSignal.emit("INFO", "Fetch", f"Fetching data for row {row + 1}")

    def _on_parse_clicked(self, row: int):
        """Handle parse button click"""
        if row < len(self.task_data):
            task_data = self.task_data[row]
            self.parseRequested.emit(task_data)

    def _show_context_menu(self, position):
        """Show context menu"""
        item = self.itemAt(position)
        if item is None:
            return

        menu = QMenu(self)

        edit_action = QAction("Edit Task", self)
        edit_action.triggered.connect(lambda: self._edit_task(item.row()))
        menu.addAction(edit_action)

        delete_action = QAction("Delete Task", self)
        delete_action.triggered.connect(lambda: self._delete_task(item.row()))
        menu.addAction(delete_action)

        menu.addSeparator()

        copy_action = QAction("Copy Row", self)
        copy_action.triggered.connect(lambda: self._copy_row(item.row()))
        menu.addAction(copy_action)

        menu.exec_(self.mapToGlobal(position))

    def _edit_task(self, row: int):
        """Edit task data"""
        # Implement edit dialog
        pass

    def _delete_task(self, row: int):
        """Delete task"""
        if 0 <= row < len(self.task_data):
            self.task_data.pop(row)
            self.removeRow(row)

    def _copy_row(self, row: int):
        """Copy row data to clipboard"""
        # Implement clipboard copy
        pass

    def update_task_status(self, row: int, status: str, details: str = ""):
        """Update task status"""
        if row < self.rowCount():
            status_item = self.item(row, 8)
            if status_item:
                status_item.setText(status)
                self._update_status_color(status_item, status)

            # Update stored data
            if row < len(self.task_data):
                self.task_data[row]['status'] = status
                if details:
                    self.task_data[row]['status_details'] = details

    def get_all_tasks(self) -> List[Dict]:
        """Get all task data including current table values"""
        tasks = []
        for row in range(self.rowCount()):
            task = {
                'client_id': self.item(row, 0).text() if self.item(row, 0) else '',
                'fund': self.item(row, 1).text() if self.item(row, 1) else '',
                'asset_id': self.item(row, 2).text() if self.item(row, 2) else '',
                'ex_date': self.item(row, 3).text() if self.item(row, 3) else '',
                'pay_date': self.item(row, 4).text() if self.item(row, 4) else '',
                'mr_income': self.item(row, 5).text() if self.item(row, 5) else '',
                'type': self.item(row, 6).text() if self.item(row, 6) else '',
                'status': self.item(row, 8).text() if self.item(row, 8) else 'Pending'
            }

            # Add original data if available
            if row < len(self.task_data):
                task.update(self.task_data[row])

            tasks.append(task)

        return tasks


class MrUpdateInterface(BaseInterface):
    """MR Update interface for managing and submitting tasks to DMH system"""

    def __init__(self, parent=None):
        super().__init__(
            title="MR Update - Task Management",
            subtitle="Manage and submit MR tasks to DMH system",
            parent=parent
        )
        self.setObjectName('mrUpdateInterface')
        self.parent_window = parent
        self.db_manager: Optional[DatabaseManager] = None
        self.dmh_service: Optional[DMH] = None
        self.current_submission_task: Optional[asyncio.Task] = None

        self._init_services()
        self._setup_ui()
        self._connect_signals()

    def _init_services(self):
        """Initialize database manager and DMH service"""
        try:
            self.db_manager = DatabaseManager(DatabaseConfig(path=CONFIG.database.path))
            self.db_manager.initialize()

            # Get DMH service from parent window
            if hasattr(self.parent_window, 'dmh'):
                self.dmh_service = self.parent_window.dmh

            logger.info("MR Update services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MR Update services: {e}")
            signalBus.infoBarSignal.emit("ERROR", "Initialization Error",
                                         f"Failed to initialize services: {str(e)}")

    def _setup_ui(self):
        """Set up the MR Update interface"""
        # Task Input Section
        self._create_task_input_section()

        # Task Table Section
        self._create_task_table_section()

        # Action Controls Section
        self._create_action_section()

        # Status and Log Section
        self._create_status_section()

    def _create_task_input_section(self):
        """Create task input section for manual task entry"""
        input_widget = QWidget()
        layout = QVBoxLayout(input_widget)

        # Manual task entry form
        form_layout = QHBoxLayout()

        # Client ID
        form_layout.addWidget(BodyLabel("Client ID:"))
        self.client_id_input = LineEdit()
        self.client_id_input.setPlaceholderText("e.g., AURR")
        form_layout.addWidget(self.client_id_input)

        # Fund
        form_layout.addWidget(BodyLabel("Fund:"))
        self.fund_input = LineEdit()
        self.fund_input.setPlaceholderText("e.g., REUC")
        form_layout.addWidget(self.fund_input)

        # Asset ID
        form_layout.addWidget(BodyLabel("Asset ID:"))
        self.asset_id_input = LineEdit()
        self.asset_id_input.setPlaceholderText("e.g., 902XGW000")
        form_layout.addWidget(self.asset_id_input)

        # Ex Date
        form_layout.addWidget(BodyLabel("Ex Date:"))
        self.ex_date_input = LineEdit()
        self.ex_date_input.setPlaceholderText("YYYYMMDD")
        form_layout.addWidget(self.ex_date_input)

        # Pay Date
        form_layout.addWidget(BodyLabel("Pay Date:"))
        self.pay_date_input = LineEdit()
        self.pay_date_input.setPlaceholderText("YYYYMMDD")
        form_layout.addWidget(self.pay_date_input)

        layout.addLayout(form_layout)

        # Second row
        form_layout2 = QHBoxLayout()

        # MR Income
        form_layout2.addWidget(BodyLabel("MR Income:"))
        self.mr_income_input = LineEdit()
        self.mr_income_input.setPlaceholderText("e.g., 0.89")
        form_layout2.addWidget(self.mr_income_input)

        # Type
        form_layout2.addWidget(BodyLabel("Type:"))
        self.type_combo = ComboBox()
        self.type_combo.addItems(["Other", "Last Actual", "Template - PIII", "Estimated"])
        form_layout2.addWidget(self.type_combo)

        # Add button
        self.add_task_btn = PushButton(FIF.ADD, "Add Task")
        self.add_task_btn.clicked.connect(self._add_manual_task)
        form_layout2.addWidget(self.add_task_btn)

        form_layout2.addStretch()
        layout.addLayout(form_layout2)

        # Bulk paste section
        paste_layout = QHBoxLayout()
        paste_layout.addWidget(BodyLabel("Bulk Paste:"))

        self.bulk_paste_text = TextEdit()
        self.bulk_paste_text.setMaximumHeight(80)
        self.bulk_paste_text.setPlaceholderText(
            "Paste tab-separated data here (Client_ID, Fund, Asset_ID, Ex_Date, Pay_Date, MR_Income, Type)")
        paste_layout.addWidget(self.bulk_paste_text)

        self.paste_btn = PushButton(FIF.PASTE, "Parse & Add")
        self.paste_btn.clicked.connect(self._parse_bulk_data)
        paste_layout.addWidget(self.paste_btn)

        layout.addLayout(paste_layout)

        self.addPageBody("Task Input", input_widget)

    def _create_task_table_section(self):
        """Create task table section"""
        table_widget = QWidget()
        layout = QVBoxLayout(table_widget)

        # Table controls
        controls_layout = QHBoxLayout()

        self.clear_table_btn = PushButton(FIF.DELETE, "Clear All")
        self.clear_table_btn.clicked.connect(self._clear_all_tasks)
        controls_layout.addWidget(self.clear_table_btn)

        self.import_csv_btn = PushButton(FIF.FOLDER, "Import CSV")
        self.import_csv_btn.clicked.connect(self._import_csv)
        controls_layout.addWidget(self.import_csv_btn)

        self.export_csv_btn = PushButton(FIF.SAVE, "Export CSV")
        self.export_csv_btn.clicked.connect(self._export_csv)
        controls_layout.addWidget(self.export_csv_btn)

        controls_layout.addStretch()

        # Task count label
        self.task_count_label = BodyLabel("Tasks: 0")
        controls_layout.addWidget(self.task_count_label)

        layout.addLayout(controls_layout)

        # Task table
        self.task_table = MRTaskTableWidget()
        self.task_table.parseRequested.connect(self._handle_parse_request)
        layout.addWidget(self.task_table)

        self.addPageBody("Task Management", table_widget)

    def _create_action_section(self):
        """Create action controls section"""
        action_widget = QWidget()
        layout = QHBoxLayout(action_widget)

        # Submit to DMH button
        self.submit_btn = PrimaryPushButton(FIF.SEND, "Submit to DMH")
        self.submit_btn.clicked.connect(self._submit_to_dmh)
        layout.addWidget(self.submit_btn)

        # Validate tasks button
        self.validate_btn = PushButton(FIF.ACCEPT, "Validate Tasks")
        self.validate_btn.clicked.connect(self._validate_tasks)
        layout.addWidget(self.validate_btn)

        layout.addStretch()

        # Progress bar
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumWidth(200)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = BodyLabel("Ready")
        layout.addWidget(self.status_label)

        self.addPageBody("Actions", action_widget)

    def _create_status_section(self):
        """Create status and log section"""
        status_widget = QWidget()
        layout = QVBoxLayout(status_widget)

        # Submission log
        log_layout = QHBoxLayout()
        log_layout.addWidget(StrongBodyLabel("Submission Log:"))

        self.clear_log_btn = PushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self._clear_log)
        log_layout.addWidget(self.clear_log_btn)
        log_layout.addStretch()

        layout.addLayout(log_layout)

        self.log_output = TextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        layout.addWidget(self.log_output)

        self.addPageBody("Status & Logs", status_widget)

    def _connect_signals(self):
        """Connect signals"""
        # Table changes
        self.task_table.itemChanged.connect(self._on_table_changed)

    @raise_error_bar_in_class
    def _add_manual_task(self):
        """Add manual task to table"""
        # Validate inputs
        if not all([
            self.client_id_input.text().strip(),
            self.fund_input.text().strip(),
            self.asset_id_input.text().strip(),
            self.ex_date_input.text().strip(),
            self.pay_date_input.text().strip(),
            self.mr_income_input.text().strip()
        ]):
            signalBus.infoBarSignal.emit("WARNING", "Incomplete Data",
                                         "Please fill all required fields")
            return

        # Create task data
        task_data = {
            'client_id': self.client_id_input.text().strip(),
            'fund': self.fund_input.text().strip(),
            'asset_id': self.asset_id_input.text().strip(),
            'ex_date': self.ex_date_input.text().strip(),
            'pay_date': self.pay_date_input.text().strip(),
            'mr_income': self.mr_income_input.text().strip(),
            'type': self.type_combo.currentText(),
            'status': 'Pending',
            'created_timestamp': datetime.now().isoformat(),
            'source': 'manual_entry'
        }

        # Add to table
        self.task_table.add_task(task_data)
        self._update_task_count()

        # Clear inputs
        self._clear_input_fields()

        signalBus.infoBarSignal.emit("SUCCESS", "Task Added", "Manual task added successfully")

    @raise_error_bar_in_class
    def _parse_bulk_data(self):
        """Parse bulk pasted data"""
        text = self.bulk_paste_text.toPlainText().strip()
        if not text:
            signalBus.infoBarSignal.emit("WARNING", "No Data", "Please paste data first")
            return

        lines = text.split('\n')
        added_count = 0

        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue

            parts = line.split('\t')
            if len(parts) < 6:
                self._log_message(f"Line {line_num}: Insufficient columns (need 6+), skipping")
                continue

            try:
                task_data = {
                    'client_id': parts[0].strip(),
                    'fund': parts[1].strip(),
                    'asset_id': parts[2].strip(),
                    'ex_date': parts[3].strip(),
                    'pay_date': parts[4].strip(),
                    'mr_income': parts[5].strip(),
                    'type': parts[6].strip() if len(parts) > 6 else 'Other',
                    'status': 'Pending',
                    'created_timestamp': datetime.now().isoformat(),
                    'source': 'bulk_paste'
                }

                self.task_table.add_task(task_data)
                added_count += 1

            except Exception as e:
                self._log_message(f"Line {line_num}: Error - {str(e)}")

        self.bulk_paste_text.clear()
        self._update_task_count()

        signalBus.infoBarSignal.emit("SUCCESS", "Bulk Import",
                                     f"Added {added_count} tasks from {len(lines)} lines")

    def receive_parsed_data(self, parsed_data: Dict[str, Any]):
        """Receive parsed data from Parser Interface"""
        # Convert parsed data to task format
        task_data = {
            'client_id': parsed_data.get('client_id', ''),
            'fund': parsed_data.get('fund', ''),
            'asset_id': parsed_data.get('asset_id', ''),
            'ex_date': parsed_data.get('ex_date', ''),
            'pay_date': parsed_data.get('pay_date', ''),
            'mr_income': parsed_data.get('mr_income_rate', ''),
            'type': 'Parsed',
            'status': 'Pending',
            'created_timestamp': datetime.now().isoformat(),
            'source': 'parser_interface',
            'source_file': parsed_data.get('source_file', ''),
            'template_used': parsed_data.get('template_used', ''),
            'parsed_data': parsed_data  # Store full parsed data
        }

        self.task_table.add_task(task_data)
        self._update_task_count()

        self._log_message(f"Received parsed data from {os.path.basename(parsed_data.get('source_file', 'parser'))}")
        signalBus.infoBarSignal.emit("SUCCESS", "Data Received", "Parsed data added to task list")

    def receive_bulk_parsed_data(self, parsed_data_list: List[Dict[str, Any]]):
        """Receive bulk parsed data from Parser Interface"""
        for parsed_data in parsed_data_list:
            self.receive_parsed_data(parsed_data)

        signalBus.infoBarSignal.emit("SUCCESS", "Bulk Data Received",
                                     f"Added {len(parsed_data_list)} parsed tasks")

    @raise_error_bar_in_class
    def _validate_tasks(self):
        """Validate all tasks"""
        tasks = self.task_table.get_all_tasks()
        if not tasks:
            signalBus.infoBarSignal.emit("WARNING", "No Tasks", "No tasks to validate")
            return

        validation_errors = []

        for i, task in enumerate(tasks):
            errors = []

            # Basic validation
            if not task.get('client_id'):
                errors.append("Missing Client ID")
            if not task.get('asset_id'):
                errors.append("Missing Asset ID")
            if not task.get('ex_date'):
                errors.append("Missing Ex Date")
            elif not self._validate_date_format(task['ex_date']):
                errors.append("Invalid Ex Date format")
            if not task.get('pay_date'):
                errors.append("Missing Pay Date")
            elif not self._validate_date_format(task['pay_date']):
                errors.append("Invalid Pay Date format")
            if not task.get('mr_income'):
                errors.append("Missing MR Income")
            elif not self._validate_numeric(task['mr_income']):
                errors.append("Invalid MR Income value")

            if errors:
                validation_errors.append(f"Row {i + 1}: {', '.join(errors)}")
                self.task_table.update_task_status(i, "Validation Error", ', '.join(errors))
            else:
                self.task_table.update_task_status(i, "Valid")

        if validation_errors:
            self._log_message("Validation completed with errors:")
            for error in validation_errors:
                self._log_message(f"  - {error}")
            signalBus.infoBarSignal.emit("WARNING", "Validation Errors",
                                         f"Found {len(validation_errors)} validation errors")
        else:
            self._log_message("All tasks passed validation")
            signalBus.infoBarSignal.emit("SUCCESS", "Validation Complete",
                                         "All tasks are valid")

    def _validate_date_format(self, date_str: str) -> bool:
        """Validate date format (YYYYMMDD)"""
        try:
            if len(date_str) != 8:
                return False
            datetime.strptime(date_str, "%Y%m%d")
            return True
        except ValueError:
            return False

    def _validate_numeric(self, value_str: str) -> bool:
        """Validate numeric value"""
        try:
            float(value_str)
            return True
        except ValueError:
            return False

    @raise_error_bar_in_class
    def _submit_to_dmh(self):
        """Submit tasks to DMH system"""
        if self.current_submission_task and not self.current_submission_task.done():
            signalBus.infoBarSignal.emit("WARNING", "Submission in Progress",
                                         "Another submission is already running")
            return

        tasks = self.task_table.get_all_tasks()
        if not tasks:
            signalBus.infoBarSignal.emit("WARNING", "No Tasks", "No tasks to submit")
            return

        # Filter valid tasks only
        valid_tasks = [task for task in tasks if task.get('status') != 'Validation Error']
        if not valid_tasks:
            signalBus.infoBarSignal.emit("WARNING", "No Valid Tasks",
                                         "No valid tasks to submit. Please validate first.")
            return

        self.current_submission_task = asyncio.create_task(self._submit_tasks_async(valid_tasks))

    async def _submit_tasks_async(self, tasks: List[Dict]):
        """Submit tasks to DMH system asynchronously"""
        try:
            self.submit_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(tasks))
            self.progress_bar.setValue(0)
            self.status_label.setText("Submitting to DMH...")

            self._log_message(f"Starting submission of {len(tasks)} tasks to DMH system")

            successful_submissions = 0
            failed_submissions = 0

            for i, task in enumerate(tasks):
                try:
                    # Update progress
                    self.progress_bar.setValue(i)
                    self.status_label.setText(f"Submitting task {i + 1}/{len(tasks)}...")

                    # Find the table row for this task
                    row_index = i  # Assuming tasks are in same order as table

                    # Update status to processing
                    self.task_table.update_task_status(row_index, "Processing")

                    # Submit to DMH
                    if self.dmh_service:
                        result = await self._submit_single_task(task)

                        if result.get('success', False):
                            self.task_table.update_task_status(row_index, "Success")
                            successful_submissions += 1

                            # Create backup file
                            await self._create_backup_file(task)

                            self._log_message(f"✓ Task {i + 1} submitted successfully: {task.get('asset_id', 'N/A')}")
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            self.task_table.update_task_status(row_index, "Failed", error_msg)
                            failed_submissions += 1
                            self._log_message(f"✗ Task {i + 1} failed: {error_msg}")
                    else:
                        self.task_table.update_task_status(row_index, "Failed", "DMH service not available")
                        failed_submissions += 1
                        self._log_message(f"✗ Task {i + 1} failed: DMH service not available")

                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.5)

                except Exception as e:
                    self.task_table.update_task_status(row_index, "Failed", str(e))
                    failed_submissions += 1
                    self._log_message(f"✗ Task {i + 1} failed with exception: {str(e)}")

            # Final status update
            self.progress_bar.setValue(len(tasks))
            self.status_label.setText("Submission completed")

            self._log_message(f"Submission completed: {successful_submissions} successful, {failed_submissions} failed")

            if failed_submissions > 0:
                signalBus.infoBarSignal.emit("WARNING", "Submission Complete",
                                             f"Completed with {failed_submissions} failures")
            else:
                signalBus.infoBarSignal.emit("SUCCESS", "Submission Complete",
                                             f"All {successful_submissions} tasks submitted successfully")

        except Exception as e:
            logger.error(f"Submission process failed: {e}")
            self.status_label.setText("Submission failed")
            signalBus.infoBarSignal.emit("ERROR", "Submission Error", f"Submission failed: {str(e)}")
        finally:
            self.submit_btn.setEnabled(True)
            self.progress_bar.setVisible(False)

    async def _submit_single_task(self, task: Dict) -> Dict:
        """Submit a single task to DMH system"""
        try:
            # Prepare DMH data format
            dmh_data = {
                'client_id': task.get('client_id'),
                'fund': task.get('fund'),
                'asset_id': task.get('asset_id'),
                'ex_date': task.get('ex_date'),
                'pay_date': task.get('pay_date'),
                'mr_income': float(task.get('mr_income', 0)),
                'type': task.get('type'),
                'user': USERNAME,
                'timestamp': datetime.now().isoformat()
            }

            # Add parsed data if available
            if 'parsed_data' in task:
                dmh_data['parsed_data'] = task['parsed_data']

            # Submit via DMH service
            # Note: This is a placeholder - implement actual DMH submission logic
            success = await self._mock_dmh_submission(dmh_data)

            if success:
                # Log to system log
                if self.db_manager:
                    with self.db_manager.session() as session:
                        log_entry = SystemLog(
                            user_id=USERNAME,
                            action="dmh_mr_submit",
                            detail=f"Asset: {task.get('asset_id')}, Amount: {task.get('mr_income')}",
                            success=True
                        )
                        session.add(log_entry)

                return {'success': True}
            else:
                return {'success': False, 'error': 'DMH submission failed'}

        except Exception as e:
            logger.error(f"Single task submission failed: {e}")
            return {'success': False, 'error': str(e)}

    async def _mock_dmh_submission(self, dmh_data: Dict) -> bool:
        """Mock DMH submission for testing - replace with actual DMH API call"""
        # Simulate network delay
        await asyncio.sleep(1)

        # Simulate occasional failures for testing
        import random
        return random.random() > 0.1  # 90% success rate

    async def _create_backup_file(self, task: Dict):
        """Create backup file for successful submission"""
        try:
            if not task.get('source_file'):
                return

            source_file = Path(task['source_file'])
            if not source_file.exists():
                return

            # Generate backup filename: {Asset_ID}_{Client_ID}_{Ex_Date in %d%b%Y format}_{EST or ACT}
            ex_date = task.get('ex_date', '')
            if len(ex_date) == 8:  # YYYYMMDD format
                try:
                    date_obj = datetime.strptime(ex_date, "%Y%m%d")
                    formatted_date = date_obj.strftime("%d%b%Y")
                except ValueError:
                    formatted_date = ex_date
            else:
                formatted_date = ex_date

            backup_filename = f"{task.get('asset_id', 'UNKNOWN')}_{task.get('client_id', 'UNKNOWN')}_{formatted_date}_ACT{source_file.suffix}"
            backup_path = CONFIG.paths.backup_path / backup_filename

            # Ensure backup directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source_file, backup_path)

            self._log_message(f"Backup created: {backup_filename}")

        except Exception as e:
            logger.error(f"Failed to create backup file: {e}")
            self._log_message(f"Warning: Failed to create backup file - {str(e)}")

    def _handle_parse_request(self, task_data: Dict):
        """Handle parse button click - redirect to Parser Interface"""
        if hasattr(self.parent_window, 'parserInterface'):
            # Switch to parser interface
            self.parent_window.switchTo(self.parent_window.parserInterface)

            # If there's a source file, load it in parser
            if task_data.get('source_file'):
                # This would require adding a method to ParserInterface to load specific files
                signalBus.infoBarSignal.emit("INFO", "Parse Request",
                                             f"Switched to Parser for {task_data.get('asset_id', 'task')}")
            else:
                signalBus.infoBarSignal.emit("INFO", "Parse Request",
                                             "Switched to Parser Interface")

    def _clear_all_tasks(self):
        """Clear all tasks from table"""
        reply = QMessageBox.question(
            self, "Clear All Tasks",
            "Are you sure you want to clear all tasks?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.task_table.setRowCount(0)
            self.task_table.task_data.clear()
            self._update_task_count()
            self._log_message("All tasks cleared")

    def _import_csv(self):
        """Import tasks from CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV File", "", "CSV Files (*.csv)"
        )

        if file_path:
            try:
                import csv
                with open(file_path, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    added_count = 0

                    for row in reader:
                        task_data = {
                            'client_id': row.get('Client_ID', ''),
                            'fund': row.get('Fund', ''),
                            'asset_id': row.get('Asset_ID', ''),
                            'ex_date': row.get('Ex_Date', ''),
                            'pay_date': row.get('Pay_Date', ''),
                            'mr_income': row.get('MR_Income', ''),
                            'type': row.get('Type', 'Other'),
                            'status': 'Pending',
                            'created_timestamp': datetime.now().isoformat(),
                            'source': 'csv_import'
                        }

                        self.task_table.add_task(task_data)
                        added_count += 1

                self._update_task_count()
                signalBus.infoBarSignal.emit("SUCCESS", "Import Complete",
                                             f"Imported {added_count} tasks from CSV")

            except Exception as e:
                signalBus.infoBarSignal.emit("ERROR", "Import Error",
                                             f"Failed to import CSV: {str(e)}")

    def _export_csv(self):
        """Export tasks to CSV file"""
        tasks = self.task_table.get_all_tasks()
        if not tasks:
            signalBus.infoBarSignal.emit("WARNING", "No Data", "No tasks to export")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV File", f"mr_tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )

        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as file:
                    fieldnames = ['Client_ID', 'Fund', 'Asset_ID', 'Ex_Date', 'Pay_Date', 'MR_Income', 'Type', 'Status']
                    writer = csv.DictWriter(file, fieldnames=fieldnames)

                    writer.writeheader()
                    for task in tasks:
                        writer.writerow({
                            'Client_ID': task.get('client_id', ''),
                            'Fund': task.get('fund', ''),
                            'Asset_ID': task.get('asset_id', ''),
                            'Ex_Date': task.get('ex_date', ''),
                            'Pay_Date': task.get('pay_date', ''),
                            'MR_Income': task.get('mr_income', ''),
                            'Type': task.get('type', ''),
                            'Status': task.get('status', '')
                        })

                signalBus.infoBarSignal.emit("SUCCESS", "Export Complete",
                                             f"Exported {len(tasks)} tasks to CSV")

            except Exception as e:
                signalBus.infoBarSignal.emit("ERROR", "Export Error",
                                             f"Failed to export CSV: {str(e)}")

    def _clear_input_fields(self):
        """Clear all input fields"""
        self.client_id_input.clear()
        self.fund_input.clear()
        self.asset_id_input.clear()
        self.ex_date_input.clear()
        self.pay_date_input.clear()
        self.mr_income_input.clear()
        self.type_combo.setCurrentIndex(0)

    def _update_task_count(self):
        """Update task count label"""
        count = self.task_table.rowCount()
        self.task_count_label.setText(f"Tasks: {count}")

    def _on_table_changed(self, item):
        """Handle table item changes"""
        # Update stored task data when table is edited
        row = item.row()
        col = item.column()

        if row < len(self.task_table.task_data):
            field_mapping = {
                0: 'client_id', 1: 'fund', 2: 'asset_id', 3: 'ex_date',
                4: 'pay_date', 5: 'mr_income', 6: 'type', 8: 'status'
            }

            if col in field_mapping:
                self.task_table.task_data[row][field_mapping[col]] = item.text()

    def _log_message(self, message: str):
        """Add message to log output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def _clear_log(self):
        """Clear log output"""
        self.log_output.clear()

    def refresh(self):
        """Refresh the view"""
        self._update_task_count()
        signalBus.infoBarSignal.emit("SUCCESS", "Refresh Complete", "MR Update view refreshed")