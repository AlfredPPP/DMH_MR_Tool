# src/dmh_mr_tool/ui/views/spider_view.py
"""Spider interface for web scraping and data collection"""

from datetime import datetime, date
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QDateEdit,
    QTableWidget, QTableWidgetItem, QComboBox,
    QProgressBar, QTextEdit, QSplitter,
    QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QDate
from PySide6.QtGui import QFont
import structlog

from ...business.services.spider_service import SpiderService
from ..widgets.data_card import DataCard

logger = structlog.get_logger()


class SpiderWorker(QThread):
    """Worker thread for spider operations"""

    # Signals
    progress = Signal(int, str)  # progress percentage, message
    finished = Signal(dict)  # results
    error = Signal(str)  # error message
    log_message = Signal(str)  # log output

    def __init__(self, operation: str, params: Dict[str, Any]):
        super().__init__()
        self.operation = operation
        self.params = params
        self.spider_service = SpiderService()

    def run(self):
        """Execute spider operation"""
        try:
            self.log_message.emit(f"Starting {self.operation}...")

            if self.operation == "daily_update":
                result = self._run_daily_update()
            elif self.operation == "single_date":
                result = self._run_single_date()
            elif self.operation == "by_ticker":
                result = self._run_by_ticker()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")

            self.finished.emit(result)

        except Exception as e:
            logger.error(f"Spider operation failed", operation=self.operation, error=str(e))
            self.error.emit(str(e))

    def _run_daily_update(self) -> Dict[str, Any]:
        """Run daily update process"""
        results = {
            "asx": {"count": 0, "errors": []},
            "vanguard": {"count": 0, "errors": []},
            "betashares": {"count": 0, "errors": []}
        }

        # Update ASX
        self.progress.emit(10, "Fetching ASX announcements...")
        try:
            asx_count = self.spider_service.fetch_asx_daily()
            results["asx"]["count"] = asx_count
            self.log_message.emit(f"Fetched {asx_count} ASX announcements")
        except Exception as e:
            results["asx"]["errors"].append(str(e))
            self.log_message.emit(f"ASX fetch failed: {e}")

        # Update Vanguard
        self.progress.emit(40, "Fetching Vanguard data...")
        try:
            vanguard_count = self.spider_service.fetch_vanguard_data()
            results["vanguard"]["count"] = vanguard_count
            self.log_message.emit(f"Fetched {vanguard_count} Vanguard records")
        except Exception as e:
            results["vanguard"]["errors"].append(str(e))
            self.log_message.emit(f"Vanguard fetch failed: {e}")

        # Update BetaShares
        self.progress.emit(70, "Fetching BetaShares data...")
        try:
            betashares_count = self.spider_service.fetch_betashares_data()
            results["betashares"]["count"] = betashares_count
            self.log_message.emit(f"Fetched {betashares_count} BetaShares announcements")
        except Exception as e:
            results["betashares"]["errors"].append(str(e))
            self.log_message.emit(f"BetaShares fetch failed: {e}")

        self.progress.emit(100, "Daily update complete")
        return results

    def _run_single_date(self) -> Dict[str, Any]:
        """Fetch data for a single date"""
        website = self.params["website"]
        target_date = self.params["date"]

        self.progress.emit(50, f"Fetching {website} data for {target_date}...")

        if website == "ASX":
            count = self.spider_service.fetch_asx_by_date(target_date)
        elif website == "Vanguard":
            count = self.spider_service.fetch_vanguard_by_date(target_date)
        elif website == "BetaShares":
            count = self.spider_service.fetch_betashares_by_date(target_date)
        else:
            raise ValueError(f"Unknown website: {website}")

        self.progress.emit(100, "Fetch complete")
        return {"count": count, "website": website, "date": target_date}

    def _run_by_ticker(self) -> Dict[str, Any]:
        """Fetch data by ticker"""
        website = self.params["website"]
        ticker = self.params["ticker"]

        self.progress.emit(50, f"Fetching {website} data for {ticker}...")

        if website == "ASX":
            count = self.spider_service.fetch_asx_by_ticker(ticker)
        else:
            raise ValueError(f"Ticker search not supported for {website}")

        self.progress.emit(100, "Fetch complete")
        return {"count": count, "website": website, "ticker": ticker}


class SpiderView(QWidget):
    """Spider interface view"""

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.worker_thread: Optional[SpiderWorker] = None
        self.last_update_times = {}
        self._setup_ui()
        self._load_update_times()

    def _setup_ui(self):
        """Set up the spider interface"""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Spider - Data Collection")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        # Top controls
        controls_layout = QHBoxLayout()

        # Daily update button
        self.daily_update_btn = QPushButton("🔄 Run Daily Update")
        self.daily_update_btn.setMinimumHeight(40)
        self.daily_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #2A82DA;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1E5FA8;
            }
        """)
        self.daily_update_btn.clicked.connect(self.run_daily_update)
        controls_layout.addWidget(self.daily_update_btn)

        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Main content splitter
        splitter = QSplitter(Qt.Vertical)

        # Cards area
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)

        # Data source cards
        self.asx_card = self._create_data_card("ASX", "asx")
        self.vanguard_card = self._create_data_card("Vanguard", "vanguard")
        self.betashares_card = self._create_data_card("BetaShares", "betashares")

        cards_layout.addWidget(self.asx_card)
        cards_layout.addWidget(self.vanguard_card)
        cards_layout.addWidget(self.betashares_card)

        splitter.addWidget(cards_widget)

        # Database info
        db_info_group = QGroupBox("Database Information")
        db_info_layout = QVBoxLayout(db_info_group)

        self.db_info_table = QTableWidget()
        self.db_info_table.setColumnCount(2)
        self.db_info_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.db_info_table.horizontalHeader().setStretchLastSection(True)
        self._populate_db_info()

        db_info_layout.addWidget(self.db_info_table)
        splitter.addWidget(db_info_group)

        # Log output
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        log_layout.addWidget(self.log_output)

        splitter.addWidget(log_group)

        layout.addWidget(splitter)

    def _create_data_card(self, title: str, source: str) -> QGroupBox:
        """Create a data source card"""
        card = QGroupBox(title)
        layout = QVBoxLayout(card)

        # Last update time
        update_label = QLabel(f"Last Update: {self.last_update_times.get(source, 'Never')}")
        update_label.setObjectName(f"{source}_update_label")
        layout.addWidget(update_label)

        # Single date fetch
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Date:"))

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())
        date_edit.setObjectName(f"{source}_date")
        date_layout.addWidget(date_edit)

        fetch_date_btn = QPushButton("Fetch")
        fetch_date_btn.clicked.connect(lambda: self.fetch_single_date(source))
        date_layout.addWidget(fetch_date_btn)

        layout.addLayout(date_layout)

        # Ticker fetch (ASX only)
        if source == "asx":
            ticker_layout = QHBoxLayout()
            ticker_layout.addWidget(QLabel("Ticker:"))

            ticker_input = QLineEdit()
            ticker_input.setPlaceholderText("e.g., FLO")
            ticker_input.setObjectName(f"{source}_ticker")
            ticker_layout.addWidget(ticker_input)

            fetch_ticker_btn = QPushButton("Fetch")
            fetch_ticker_btn.clicked.connect(lambda: self.fetch_by_ticker(source))
            ticker_layout.addWidget(fetch_ticker_btn)

            layout.addLayout(ticker_layout)

        return card

    def _populate_db_info(self):
        """Populate database information table"""
        db_config = self.parent_window.app.config_manager.config.database

        info = [
            ("Database Path", str(db_config.path)),
            ("Backup Path", str(db_config.backup_path)),
            ("Tables", "asx_info, asx_nz_data, vanguard_data, vanguard_mapping, column_map, sys_log"),
            ("Connection Pool Size", str(db_config.pool_size))
        ]

        self.db_info_table.setRowCount(len(info))
        for i, (key, value) in enumerate(info):
            self.db_info_table.setItem(i, 0, QTableWidgetItem(key))
            self.db_info_table.setItem(i, 1, QTableWidgetItem(value))

    def _load_update_times(self):
        """Load last update times from database"""
        # This would query the database for last update times
        # For now, using placeholder data
        self.last_update_times = {
            "asx": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "vanguard": "2025-01-15 09:30",
            "betashares": "2025-01-14 14:15"
        }

    def run_daily_update(self):
        """Run the daily update process"""
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Operation in Progress",
                                "Another operation is already running.")
            return

        self.daily_update_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_output.clear()

        self.worker_thread = SpiderWorker("daily_update", {})
        self.worker_thread.progress.connect(self._on_progress)
        self.worker_thread.finished.connect(self._on_daily_update_complete)
        self.worker_thread.error.connect(self._on_error)
        self.worker_thread.log_message.connect(self._on_log_message)
        self.worker_thread.start()

    def fetch_single_date(self, source: str):
        """Fetch data for a single date"""
        date_edit = self.findChild(QDateEdit, f"{source}_date")
        if not date_edit:
            return

        target_date = date_edit.date().toPython()

        self.worker_thread = SpiderWorker("single_date", {
            "website": source.title(),
            "date": target_date
        })
        self.worker_thread.progress.connect(self._on_progress)
        self.worker_thread.finished.connect(self._on_fetch_complete)
        self.worker_thread.error.connect(self._on_error)
        self.worker_thread.log_message.connect(self._on_log_message)
        self.worker_thread.start()

    def fetch_by_ticker(self, source: str):
        """Fetch data by ticker"""
        ticker_input = self.findChild(QLineEdit, f"{source}_ticker")
        if not ticker_input:
            return

        ticker = ticker_input.text().strip().upper()
        if not ticker:
            QMessageBox.warning(self, "Input Error", "Please enter a ticker code.")
            return

        self.worker_thread = SpiderWorker("by_ticker", {
            "website": source.upper(),
            "ticker": ticker
        })
        self.worker_thread.progress.connect(self._on_progress)
        self.worker_thread.finished.connect(self._on_fetch_complete)
        self.worker_thread.error.connect(self._on_error)
        self.worker_thread.log_message.connect(self._on_log_message)
        self.worker_thread.start()

    def _on_progress(self, value: int, message: str):
        """Handle progress update"""
        self.progress_bar.setValue(value)
        self.status_message.emit(message)

    def _on_daily_update_complete(self, results: dict):
        """Handle daily update completion"""
        self.daily_update_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        # Update last update times
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for source in ["asx", "vanguard", "betashares"]:
            self.last_update_times[source] = now
            label = self.findChild(QLabel, f"{source}_update_label")
            if label:
                label.setText(f"Last Update: {now}")

        # Show summary
        total = sum(r["count"] for r in results.values())
        errors = sum(len(r["errors"]) for r in results.values())

        message = f"Daily update complete: {total} records fetched"
        if errors > 0:
            message += f" ({errors} errors)"

        self.status_message.emit(message)
        self._on_log_message(message)

    def _on_fetch_complete(self, results: dict):
        """Handle single fetch completion"""
        self.progress_bar.setVisible(False)

        count = results.get("count", 0)
        website = results.get("website", "")

        message = f"Fetched {count} records from {website}"
        self.status_message.emit(message)
        self._on_log_message(message)

    def _on_error(self, error_message: str):
        """Handle error"""
        self.daily_update_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        QMessageBox.critical(self, "Operation Failed", error_message)
        self._on_log_message(f"ERROR: {error_message}")

    def _on_log_message(self, message: str):
        """Add message to log output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def refresh(self):
        """Refresh the view"""
        self._load_update_times()
        self._populate_db_info()
        self.status_message.emit("Spider view refreshed")