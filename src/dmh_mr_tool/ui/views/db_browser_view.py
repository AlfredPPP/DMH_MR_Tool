import asyncio
import sys

from Demos.EvtSubscribe_pull import query_text
from PySide6.QtCore import Qt
from PySide6.QtSql import QSqlQueryModel, QSqlDatabase
from PySide6.QtWidgets import QSplitter, QHeaderView, QVBoxLayout
from qfluentwidgets import TextEdit, PushButton, TableView

from config.settings import CONFIG
from ui.utils.signal_bus import signalBus
from ui.views.base_view import BaseInterface


class DBBrowserInterface(BaseInterface):
    def __init__(self, parent=None):
        super().__init__(title="Database Browser", subtitle="Browse and query the database", parent=parent)
        self.setObjectName('dbBrowserInterface')
        self.infoBarSignal = signalBus.infoBarSignal

        self.db_address = CONFIG.database.path
        self.setWindowTitle("DB Browser for SQLite")
        self.resize(800, 600)

        spliter = QSplitter(Qt.Orientation.Vertical)

        self.query_input = TextEdit(self)
        self.query_input.setPlaceholderText("Enter your SQL query here...")

        self.run_button = PushButton("Run Query")
        self.run_button.clicked.connect(self.run_query)

        self.table_view = TableView(self)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.model = SortableSqlModel()
        self.table_view.setModel(self.model)
        self.table_view.setSortingEnabled(True)
        self.run_button.setFixedHeight(40)

        spliter.addWidget(self.query_input)
        spliter.addWidget(self.run_button)
        spliter.addWidget(self.table_view)

        layout = QVBoxLayout(self)
        layout.addSpacing(20)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.addWidget(spliter)

        self.setLayout(layout)
        self.init_db()

    def init_db(self):
        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(self.db_address.__str__())
        if not self.db.open():
            self.infoBarSignal.emit("ERROR", "Database Not Found",
                                    f"Failed to connect to database: {self.db.lastError().text()}")

    def run_query(self):
        query_text = self.query_input.toPlainText().strip()
        self.model.setBaseQuery(query_text)
        if self.model.lastError().isValid():
            self.infoBarSignal.emit("WARNING", "Query Error", self.model.lastError().text())


class SortableSqlModel(QSqlQueryModel):
    def __init__(self):
        super().__init__()
        self._base_sql = ""

    def setBaseQuery(self, sql):
        self._base_sql = sql
        self.setQuery(sql)

    def sort(self, column, order=...):
        if not hasattr(self, "_base_sql"):
            return
        column_name = self.headerData(column, Qt.Orientation.Horizontal)
        order_sql = f"{self._base_sql} ORDER BY {column_name} {'ASC' if order == Qt.SortOrder.AscendingOrder else 'DESC'}"
        self.setQuery(order_sql)
