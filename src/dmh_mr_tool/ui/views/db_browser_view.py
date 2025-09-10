# src/dmh_mr_tool/ui/views/db_browser_view.py
"""Database Browser Interface for querying and viewing database content"""

import re
import os
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtSql import QSqlQueryModel, QSqlDatabase, QSqlQuery
from PySide6.QtWidgets import (
    QSplitter, QHeaderView, QVBoxLayout, QHBoxLayout, QWidget,
    QTableView, QAbstractItemView, QFileDialog, QMessageBox,
    QApplication
)
from qfluentwidgets import (
    TextEdit, PrimaryPushButton, PushButton, ComboBox,
    StrongBodyLabel, BodyLabel, CaptionLabel, CardWidget,
    InfoBar, InfoBarPosition, FluentIcon as FIF
)

from config.settings import CONFIG
from core.utils import USERNAME
from ui.utils.signal_bus import signalBus
from ui.utils.infobar import raise_error_bar_in_class, createWarningInfoBar, createSuccessInfoBar, createErrorInfoBar
from ui.views.base_view import BaseInterface, SeparatorWidget

import structlog

logger = structlog.get_logger()


class SortableSqlModel(QSqlQueryModel):
    """Enhanced SQL model with sorting capability"""

    def __init__(self):
        super().__init__()
        self._base_sql = ""
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder

    def setBaseQuery(self, sql: str):
        """Set the base SQL query"""
        self._base_sql = sql.strip()
        self.setQuery(sql)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        """Sort the model by column"""
        if not self._base_sql or column < 0:
            return

        try:
            column_name = self.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            if not column_name:
                return

            self._sort_column = column
            self._sort_order = order

            # Build ORDER BY clause
            order_direction = "ASC" if order == Qt.SortOrder.AscendingOrder else "DESC"

            # Remove existing ORDER BY clause if present
            base_sql = re.sub(r'\s+ORDER\s+BY\s+.*$', '', self._base_sql, flags=re.IGNORECASE)

            order_sql = f"{base_sql} ORDER BY {column_name} {order_direction}"
            self.setQuery(order_sql)

        except Exception as e:
            logger.error(f"Error sorting query: {e}")


class QueryTemplateCard(CardWidget):
    """Card widget for predefined query templates"""

    def __init__(self, title: str, description: str, query: str, parent=None):
        super().__init__(parent)
        self.query = query
        self.setupUI(title, description)

    def setupUI(self, title: str, description: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Title
        title_label = StrongBodyLabel(title, self)
        layout.addWidget(title_label)

        # Description
        desc_label = CaptionLabel(description, self)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Use button
        use_btn = PushButton("Use Query", self)
        use_btn.setIcon(FIF.PLAY)
        use_btn.clicked.connect(self.useQuery)
        layout.addWidget(use_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.setFixedHeight(120)

    def useQuery(self):
        """Emit signal to use this query"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'setQuery'):
                parent.setQuery(self.query)
                break
            parent = parent.parent()


class DBBrowserInterface(BaseInterface):
    """Database Browser Interface for querying and viewing database content"""

    # Developer usernames who can execute write operations
    DEVELOPER_USERS = ['Alfred', 'admin', 'developer']  # Add actual developer usernames

    def __init__(self, parent=None):
        super().__init__(
            title="Database Browser",
            subtitle="Query and browse database content with SQL",
            parent=parent
        )
        self.setObjectName('dbBrowserInterface')
        self.current_database = None
        self.initUI()
        self.initDatabase()
        self.loadQueryTemplates()

    def initUI(self):
        """Initialize the user interface"""
        # Main splitter
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Database selection section
        self.addDatabaseSelection()

        # Query templates section
        self.addQueryTemplates()

        # Query input section
        self.addQueryInput()

        # Results section
        self.addResultsSection()

        # Query statistics section
        self.addStatisticsSection()

        # Add to page
        self.addPageBody("", self.splitter, stretch=1)

    def addDatabaseSelection(self):
        """Add database selection section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # Database dropdown
        self.databaseCombo = ComboBox(widget)
        self.databaseCombo.setMinimumWidth(200)
        self.databaseCombo.currentTextChanged.connect(self.onDatabaseChanged)
        self.loadDatabaseList()

        # Refresh button
        refresh_btn = PushButton("Refresh", widget)
        refresh_btn.setIcon(FIF.SYNC)
        refresh_btn.clicked.connect(self.loadDatabaseList)

        # Connection status
        self.connectionLabel = BodyLabel("Not connected", widget)

        layout.addWidget(BodyLabel("Database:", widget))
        layout.addWidget(self.databaseCombo)
        layout.addWidget(refresh_btn)
        layout.addStretch()
        layout.addWidget(self.connectionLabel)

        # Add to splitter
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(StrongBodyLabel("Database Connection"))
        card_layout.addWidget(widget)
        card.setFixedHeight(80)

        self.splitter.addWidget(card)

    def addQueryTemplates(self):
        """Add predefined query templates section"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Templates container
        templates_widget = QWidget()
        templates_layout = QHBoxLayout(templates_widget)
        templates_layout.setSpacing(12)

        # Define common query templates
        templates = [
            {
                "title": "Recent ASX Announcements",
                "description": "Show the 20 most recent ASX announcements",
                "query": "SELECT asx_code, title, pub_date, downloaded, parsed FROM asx_info ORDER BY pub_date DESC LIMIT 20"
            },
            {
                "title": "Download Statistics",
                "description": "Show download status summary by ASX code",
                "query": "SELECT asx_code, COUNT(*) as total, SUM(downloaded) as downloaded FROM asx_info GROUP BY asx_code ORDER BY total DESC"
            },
            {
                "title": "System Activity Log",
                "description": "Show recent system activities",
                "query": "SELECT update_timestamp, user_id, action, success FROM sys_log ORDER BY update_timestamp DESC LIMIT 50"
            },
            {
                "title": "Vanguard Data Summary",
                "description": "Show latest Vanguard fund data",
                "query": "SELECT ticker, fund_name, as_of_date, cpu FROM vanguard_data ORDER BY as_of_date DESC LIMIT 20"
            }
        ]

        for template in templates:
            card = QueryTemplateCard(
                template["title"],
                template["description"],
                template["query"],
                templates_widget
            )
            templates_layout.addWidget(card)

        templates_layout.addStretch()

        layout.addWidget(StrongBodyLabel("Query Templates"))
        layout.addWidget(templates_widget)

        # Collapsible section
        template_card = CardWidget()
        template_card.setLayout(layout)
        template_card.setFixedHeight(150)

        self.splitter.addWidget(template_card)

    def addQueryInput(self):
        """Add SQL query input section"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Query input
        self.queryInput = TextEdit(widget)
        self.queryInput.setPlaceholderText(
            "Enter your SQL query here...\n\n"
            "Examples:\n"
            "SELECT * FROM asx_info LIMIT 10;\n"
            "SELECT asx_code, COUNT(*) FROM asx_info GROUP BY asx_code;\n"
            "\nNote: Only developers can execute INSERT/UPDATE/DELETE queries."
        )
        self.queryInput.setMinimumHeight(120)

        # Control buttons
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)

        self.runBtn = PrimaryPushButton("Run Query", controls_widget)
        self.runBtn.setIcon(FIF.PLAY)
        self.runBtn.clicked.connect(self.runQuery)

        self.clearBtn = PushButton("Clear", controls_widget)
        self.clearBtn.setIcon(FIF.DELETE)
        self.clearBtn.clicked.connect(self.queryInput.clear)

        self.exportBtn = PushButton("Export Results", controls_widget)
        self.exportBtn.setIcon(FIF.SAVE)
        self.exportBtn.clicked.connect(self.exportResults)
        self.exportBtn.setEnabled(False)

        controls_layout.addWidget(self.runBtn)
        controls_layout.addWidget(self.clearBtn)
        controls_layout.addWidget(self.exportBtn)
        controls_layout.addStretch()

        layout.addWidget(StrongBodyLabel("SQL Query"))
        layout.addWidget(self.queryInput)
        layout.addWidget(controls_widget)

        query_card = CardWidget()
        query_card.setLayout(layout)
        self.splitter.addWidget(query_card)

    def addResultsSection(self):
        """Add query results table section"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Results table
        self.tableView = QTableView(widget)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableView.setSortingEnabled(True)

        # Configure headers
        self.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tableView.horizontalHeader().setStretchLastSection(True)
        self.tableView.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Model
        self.model = SortableSqlModel()
        self.tableView.setModel(self.model)

        # Context menu for copying
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.showTableContextMenu)

        layout.addWidget(StrongBodyLabel("Query Results"))
        layout.addWidget(self.tableView)

        results_card = CardWidget()
        results_card.setLayout(layout)
        self.splitter.addWidget(results_card)

    def addStatisticsSection(self):
        """Add query statistics section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Statistics labels
        self.recordCountLabel = CaptionLabel("Records: 0", widget)
        self.executionTimeLabel = CaptionLabel("Execution time: 0ms", widget)
        self.queryTypeLabel = CaptionLabel("Query type: -", widget)

        layout.addWidget(self.recordCountLabel)
        layout.addWidget(self.executionTimeLabel)
        layout.addWidget(self.queryTypeLabel)
        layout.addStretch()

        stats_card = CardWidget()
        stats_card.setLayout(QVBoxLayout())
        stats_card.layout().addWidget(CaptionLabel("Statistics"))
        stats_card.layout().addWidget(widget)
        stats_card.setFixedHeight(60)

        self.splitter.addWidget(stats_card)

        # Set splitter proportions
        self.splitter.setSizes([80, 150, 200, 400, 60])

    def loadDatabaseList(self):
        """Load available databases"""
        self.databaseCombo.clear()

        # Add main database
        main_db_path = CONFIG.database.path
        if main_db_path.exists():
            self.databaseCombo.addItem(f"Main Database ({main_db_path.name})", str(main_db_path))

        # Add backup databases if they exist
        backup_path = CONFIG.database.backup_path
        if backup_path and backup_path.exists():
            for backup_file in backup_path.glob("*.db"):
                self.databaseCombo.addItem(f"Backup ({backup_file.name})", str(backup_file))

        # Set default selection
        if self.databaseCombo.count() > 0:
            self.databaseCombo.setCurrentIndex(0)

    def onDatabaseChanged(self):
        """Handle database selection change"""
        if self.databaseCombo.currentData():
            self.initDatabase(self.databaseCombo.currentData())

    def initDatabase(self, db_path: str = None):
        """Initialize database connection"""
        try:
            # Close existing connection
            if self.current_database:
                QSqlDatabase.removeDatabase(self.current_database)

            # Use provided path or default
            if db_path is None:
                db_path = str(CONFIG.database.path)

            # Create new connection
            connection_name = f"browser_connection_{id(self)}"
            self.db = QSqlDatabase.addDatabase("QSQLITE", connection_name)
            self.db.setDatabaseName(db_path)

            if self.db.open():
                self.current_database = connection_name
                self.connectionLabel.setText(f"Connected to: {Path(db_path).name}")
                createSuccessInfoBar(self, "Database Connected", f"Successfully connected to {Path(db_path).name}")

                # Enable query execution
                self.runBtn.setEnabled(True)

                logger.info(f"Database connected: {db_path}")
            else:
                error_msg = self.db.lastError().text()
                self.connectionLabel.setText("Connection failed")
                createErrorInfoBar(self, "Connection Failed", f"Failed to connect to database: {error_msg}")
                self.runBtn.setEnabled(False)
                logger.error(f"Database connection failed: {error_msg}")

        except Exception as e:
            self.connectionLabel.setText("Connection error")
            createErrorInfoBar(self, "Database Error", f"Database error: {str(e)}")
            self.runBtn.setEnabled(False)
            logger.error(f"Database initialization error: {e}")

    def loadQueryTemplates(self):
        """Load predefined query templates"""
        # This method can be extended to load templates from a file or database
        pass

    def setQuery(self, query: str):
        """Set query in the input field (called by template cards)"""
        self.queryInput.setPlainText(query)

    @raise_error_bar_in_class
    def runQuery(self):
        """Execute the SQL query"""
        query_text = self.queryInput.toPlainText().strip()

        if not query_text:
            createWarningInfoBar(self, "Empty Query", "Please enter a SQL query")
            return

        # Check for write operations and user permissions
        if self.isWriteOperation(query_text):
            if not self.canExecuteWriteOperations():
                createWarningInfoBar(
                    self,
                    "Permission Denied",
                    "Only developers can execute INSERT/UPDATE/DELETE queries"
                )
                return

            # Confirm write operation
            if not self.confirmWriteOperation(query_text):
                return

        try:
            # Record start time
            import time
            start_time = time.time()

            # Execute query
            self.model.setBaseQuery(query_text)

            # Calculate execution time
            execution_time = int((time.time() - start_time) * 1000)

            # Check for errors
            if self.model.lastError().isValid():
                error_msg = self.model.lastError().text()
                createErrorInfoBar(self, "Query Error", error_msg)
                self.updateStatistics(0, execution_time, "ERROR")
                return

            # Update statistics
            record_count = self.model.rowCount()
            query_type = self.getQueryType(query_text)
            self.updateStatistics(record_count, execution_time, query_type)

            # Enable export if we have results
            self.exportBtn.setEnabled(record_count > 0)

            # Show success message for write operations
            if self.isWriteOperation(query_text):
                createSuccessInfoBar(self, "Query Executed",
                                     f"Query executed successfully. Rows affected: {record_count}")

            logger.info(f"Query executed successfully",
                        query_type=query_type,
                        record_count=record_count,
                        execution_time=execution_time)

        except Exception as e:
            createErrorInfoBar(self, "Execution Error", f"Error executing query: {str(e)}")
            logger.error(f"Query execution error: {e}")

    def isWriteOperation(self, query: str) -> bool:
        """Check if query is a write operation"""
        write_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
        query_upper = query.upper().strip()

        for keyword in write_keywords:
            if query_upper.startswith(keyword):
                return True

        return False

    def canExecuteWriteOperations(self) -> bool:
        """Check if current user can execute write operations"""
        return USERNAME in self.DEVELOPER_USERS

    def confirmWriteOperation(self, query: str) -> bool:
        """Show confirmation dialog for write operations"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Write Operation")
        msg_box.setText("You are about to execute a write operation that will modify the database.")
        msg_box.setInformativeText(f"Query: {query[:100]}{'...' if len(query) > 100 else ''}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setIcon(QMessageBox.Icon.Warning)

        return msg_box.exec() == QMessageBox.StandardButton.Yes

    def getQueryType(self, query: str) -> str:
        """Determine the type of SQL query"""
        query_upper = query.upper().strip()

        if query_upper.startswith('SELECT'):
            return 'SELECT'
        elif query_upper.startswith('INSERT'):
            return 'INSERT'
        elif query_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        elif query_upper.startswith('CREATE'):
            return 'CREATE'
        elif query_upper.startswith('DROP'):
            return 'DROP'
        elif query_upper.startswith('ALTER'):
            return 'ALTER'
        else:
            return 'OTHER'

    def updateStatistics(self, record_count: int, execution_time: int, query_type: str):
        """Update query statistics display"""
        self.recordCountLabel.setText(f"Records: {record_count:,}")
        self.executionTimeLabel.setText(f"Execution time: {execution_time}ms")
        self.queryTypeLabel.setText(f"Query type: {query_type}")

    def showTableContextMenu(self, pos):
        """Show context menu for table"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)

        copy_action = QAction("Copy Selected", self)
        copy_action.triggered.connect(self.copySelected)
        menu.addAction(copy_action)

        copy_all_action = QAction("Copy All", self)
        copy_all_action.triggered.connect(self.copyAll)
        menu.addAction(copy_all_action)

        menu.exec(self.tableView.mapToGlobal(pos))

    def copySelected(self):
        """Copy selected rows to clipboard"""
        selection = self.tableView.selectionModel().selectedRows()
        if not selection:
            return

        # Get selected data
        data = []
        for index in selection:
            row_data = []
            for col in range(self.model.columnCount()):
                item = self.model.index(index.row(), col)
                row_data.append(str(self.model.data(item) or ''))
            data.append('\t'.join(row_data))

        # Copy to clipboard
        clipboard_text = '\n'.join(data)
        QApplication.clipboard().setText(clipboard_text)

        createSuccessInfoBar(self, "Copied", f"Copied {len(selection)} rows to clipboard")

    def copyAll(self):
        """Copy all results to clipboard"""
        if self.model.rowCount() == 0:
            return

        # Get headers
        headers = []
        for col in range(self.model.columnCount()):
            headers.append(
                str(self.model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or ''))

        # Get all data
        data = ['\t'.join(headers)]
        for row in range(self.model.rowCount()):
            row_data = []
            for col in range(self.model.columnCount()):
                item = self.model.index(row, col)
                row_data.append(str(self.model.data(item) or ''))
            data.append('\t'.join(row_data))

        # Copy to clipboard
        clipboard_text = '\n'.join(data)
        QApplication.clipboard().setText(clipboard_text)

        createSuccessInfoBar(self, "Copied", f"Copied all {self.model.rowCount()} rows to clipboard")

    @raise_error_bar_in_class
    def exportResults(self):
        """Export query results to CSV file"""
        if self.model.rowCount() == 0:
            createWarningInfoBar(self, "No Data", "No data to export")
            return

        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Query Results",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            import csv

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write headers
                headers = []
                for col in range(self.model.columnCount()):
                    headers.append(
                        str(self.model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or ''))
                writer.writerow(headers)

                # Write data
                for row in range(self.model.rowCount()):
                    row_data = []
                    for col in range(self.model.columnCount()):
                        item = self.model.index(row, col)
                        row_data.append(str(self.model.data(item) or ''))
                    writer.writerow(row_data)

            createSuccessInfoBar(self, "Export Complete",
                                 f"Exported {self.model.rowCount()} rows to {Path(file_path).name}")
            logger.info(f"Query results exported to {file_path}")

        except Exception as e:
            createErrorInfoBar(self, "Export Error", f"Failed to export results: {str(e)}")
            logger.error(f"Export error: {e}")

    def closeEvent(self, event):
        """Clean up database connection when closing"""
        if self.current_database:
            QSqlDatabase.removeDatabase(self.current_database)
        super().closeEvent(event)