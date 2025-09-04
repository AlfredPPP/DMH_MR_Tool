# src/dmh_mr_tool/ui/views/spider_view.py
"""Spider interface for web scraping and data collection"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QDateEdit,
    QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QSplitter,
    QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont
import structlog

from qfluentwidgets import (
    PrimaryPushButton, PushButton, BodyLabel, StrongBodyLabel,
    LineEdit, DatePicker, TableWidget, ProgressBar,
    TextEdit, CardWidget, FluentIcon as FIF,
    InfoBarPosition
)

from ui.views.base_view import BaseInterface
from ui.utils.signal_bus import signalBus
from business.services.spider_service import SpiderService

logger = structlog.get_logger()


class SpiderInterface(BaseInterface):
    """Spider interface for data collection using qasync"""

    def __init__(self, parent=None):
        super().__init__(
            title="Spider - Data Collection",
            subtitle="Web scraping and data collection tools",
            parent=parent
        )
        self.setObjectName('spiderInterface')
        self.parent_window = parent
        self.spider_service: Optional[SpiderService] = None
        self.last_update_times = {}
        self.current_operation: Optional[asyncio.Task] = None

        self._init_spider_service()
        self._setup_ui()
        self._load_update_times()
        self._connect_signals()

    def _init_spider_service(self):
        """Initialize spider service"""
        try:
            if hasattr(self.parent_window, 'dmh') and self.parent_window.dmh:
                # Assuming spider_service is available through dmh service
                self.spider_service = SpiderService(self.parent_window.dmh.db_manager)
        except Exception as e:
            logger.error(f"Failed to initialize spider service: {e}")

    def _setup_ui(self):
        """Set up the spider interface"""
        # Daily Update Section
        self._create_daily_update_section()

        # Data Source Cards Section
        self._create_data_source_section()

        # Database Info Section
        self._create_database_info_section()

        # Activity Log Section
        self._create_activity_log_section()

    def _create_daily_update_section(self):
        """Create daily update control section"""
        # Main container
        daily_update_widget = QWidget()
        layout = QVBoxLayout(daily_update_widget)

        # Title and button row
        header_layout = QHBoxLayout()

        # Daily update button
        self.daily_update_btn = PrimaryPushButton(FIF.SYNC, "Run Daily Update")
        self.daily_update_btn.setMinimumHeight(50)
        self.daily_update_btn.setMinimumWidth(200)
        self.daily_update_btn.clicked.connect(self._on_daily_update_clicked)
        header_layout.addWidget(self.daily_update_btn)

        # Progress info
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)

        self.progress_label = BodyLabel("Ready")
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)

        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)

        header_layout.addWidget(progress_widget)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        self.addPageBody("Daily Update", daily_update_widget)

    def _create_data_source_section(self):
        """Create data source cards section"""
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)

        # ASX Card
        self.asx_card = self._create_data_source_card("ASX", "asx", True)
        cards_layout.addWidget(self.asx_card)

        # Vanguard Card
        self.vanguard_card = self._create_data_source_card("Vanguard", "vanguard", False)
        cards_layout.addWidget(self.vanguard_card)

        # BetaShares Card
        self.betashares_card = self._create_data_source_card("BetaShares", "betashares", False)
        cards_layout.addWidget(self.betashares_card)

        self.addPageBody("Data Sources", cards_widget)

    def _create_data_source_card(self, title: str, source: str, supports_ticker: bool) -> CardWidget:
        """Create a data source card"""
        card = CardWidget()
        card.setMinimumHeight(200)
        layout = QVBoxLayout(card)

        # Title
        title_label = StrongBodyLabel(title)
        layout.addWidget(title_label)

        # Last update time
        update_time = self.last_update_times.get(source, "Never")
        update_label = BodyLabel(f"Last Update: {update_time}")
        update_label.setObjectName(f"{source}_update_label")
        layout.addWidget(update_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Date fetch section
        date_layout = QHBoxLayout()
        date_layout.addWidget(BodyLabel("Date:"))

        date_picker = DatePicker()
        date_picker.setDate(QDate.currentDate())
        date_picker.setObjectName(f"{source}_date")
        date_layout.addWidget(date_picker)

        fetch_date_btn = PushButton("Fetch")
        fetch_date_btn.clicked.connect(lambda: self._on_fetch_single_date_clicked(source))
        date_layout.addWidget(fetch_date_btn)

        layout.addLayout(date_layout)

        # Ticker fetch section (ASX only)
        if supports_ticker:
            ticker_layout = QHBoxLayout()
            ticker_layout.addWidget(BodyLabel("Ticker:"))

            ticker_input = LineEdit()
            ticker_input.setPlaceholderText("e.g., FLO")
            ticker_input.setObjectName(f"{source}_ticker")
            ticker_layout.addWidget(ticker_input)

            fetch_ticker_btn = PushButton("Fetch")
            fetch_ticker_btn.clicked.connect(lambda: self._on_fetch_by_ticker_clicked(source))
            ticker_layout.addWidget(fetch_ticker_btn)

            layout.addLayout(ticker_layout)

        layout.addStretch()
        return card

    def _create_database_info_section(self):
        """Create database information section"""
        db_info_table = TableWidget()
        db_info_table.setColumnCount(2)
        db_info_table.setHorizontalHeaderLabels(["Property", "Value"])
        db_info_table.horizontalHeader().setStretchLastSection(True)
        db_info_table.setMaximumHeight(200)

        self._populate_db_info(db_info_table)
        self.addPageBody("Database Information", db_info_table)

    def _create_activity_log_section(self):
        """Create activity log section"""
        self.log_output = TextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)

        self.addPageBody("Activity Log", self.log_output)

    def _populate_db_info(self, table: TableWidget):
        """Populate database information table"""
        try:
            # Get database config from parent window
            if hasattr(self.parent_window, 'dmh') and self.parent_window.dmh:
                db_config = self.parent_window.dmh.db_manager.config
                info = [
                    ("Database Path", str(getattr(db_config, 'path', 'N/A'))),
                    ("Backup Path", str(getattr(db_config, 'backup_path', 'N/A'))),
                    ("Tables", "asx_info, asx_nz_data, vanguard_data, vanguard_mapping, column_map, sys_log"),
                    ("Connection Pool Size", str(getattr(db_config, 'pool_size', 'N/A')))
                ]
            else:
                info = [
                    ("Database Path", "Not available"),
                    ("Backup Path", "Not available"),
                    ("Tables", "asx_info, asx_nz_data, vanguard_data, vanguard_mapping, column_map, sys_log"),
                    ("Connection Pool Size", "Not available")
                ]
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            info = [("Error", "Failed to load database information")]

        table.setRowCount(len(info))
        for i, (key, value) in enumerate(info):
            table.setItem(i, 0, QTableWidgetItem(key))
            table.setItem(i, 1, QTableWidgetItem(value))

    def _load_update_times(self):
        """Load last update times from database or config"""
        try:
            # This would query the database for last update times
            # For now, using placeholder data
            self.last_update_times = {
                "asx": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "vanguard": "2025-01-15 09:30",
                "betashares": "2025-01-14 14:15"
            }
        except Exception as e:
            logger.error(f"Failed to load update times: {e}")
            self.last_update_times = {}

    def _connect_signals(self):
        """Connect to signal bus"""
        signalBus.spiderProgressSignal.connect(self._on_progress)
        signalBus.spiderLogSignal.connect(self._on_log_message)

    # Sync wrapper methods for button clicks
    def _on_daily_update_clicked(self):
        """Handle daily update button click"""
        asyncio.create_task(self._run_daily_update())

    def _on_fetch_single_date_clicked(self, source: str):
        """Handle fetch single date button click"""
        asyncio.create_task(self._fetch_single_date(source))

    def _on_fetch_by_ticker_clicked(self, source: str):
        """Handle fetch by ticker button click"""
        asyncio.create_task(self._fetch_by_ticker(source))

    async def _run_daily_update(self):
        """Run the daily update process using async/await"""
        if self.current_operation and not self.current_operation.done():
            signalBus.infoBarSignal.emit("WARNING", "Operation in Progress",
                                         "Another operation is already running.")
            return

        if not self.spider_service:
            signalBus.infoBarSignal.emit("ERROR", "Service Error",
                                         "Spider service is not available.")
            return

        try:
            self.daily_update_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_label.setText("Starting daily update...")

            signalBus.spiderLogSignal.emit("Starting daily update process...")

            # Execute the daily update
            results = await self._execute_daily_update()

            self._handle_daily_update_complete(results)

        except Exception as e:
            logger.error(f"Daily update failed: {e}")
            self._handle_operation_error(str(e))
        finally:
            self.daily_update_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.progress_label.setText("Ready")

    async def _execute_daily_update(self) -> Dict[str, Any]:
        """Execute the daily update process"""
        results = {
            "asx": {"count": 0, "errors": []},
            "vanguard": {"count": 0, "errors": []},
            "betashares": {"count": 0, "errors": []}
        }

        try:
            # Update ASX
            signalBus.spiderProgressSignal.emit(10, "Fetching ASX announcements...")
            try:
                # Simulate ASX fetching - replace with actual spider service call
                await asyncio.sleep(1)  # Simulate network delay
                asx_count = await self._fetch_asx_daily()
                results["asx"]["count"] = asx_count
                signalBus.spiderLogSignal.emit(f"Fetched {asx_count} ASX announcements")
            except Exception as e:
                results["asx"]["errors"].append(str(e))
                signalBus.spiderLogSignal.emit(f"ASX fetch failed: {e}")

            # Update Vanguard
            signalBus.spiderProgressSignal.emit(40, "Fetching Vanguard data...")
            try:
                await asyncio.sleep(1)  # Simulate network delay
                vanguard_count = await self._fetch_vanguard_data()
                results["vanguard"]["count"] = vanguard_count
                signalBus.spiderLogSignal.emit(f"Fetched {vanguard_count} Vanguard records")
            except Exception as e:
                results["vanguard"]["errors"].append(str(e))
                signalBus.spiderLogSignal.emit(f"Vanguard fetch failed: {e}")

            # Update BetaShares
            signalBus.spiderProgressSignal.emit(70, "Fetching BetaShares data...")
            try:
                await asyncio.sleep(1)  # Simulate network delay
                betashares_count = await self._fetch_betashares_data()
                results["betashares"]["count"] = betashares_count
                signalBus.spiderLogSignal.emit(f"Fetched {betashares_count} BetaShares announcements")
            except Exception as e:
                results["betashares"]["errors"].append(str(e))
                signalBus.spiderLogSignal.emit(f"BetaShares fetch failed: {e}")

            signalBus.spiderProgressSignal.emit(100, "Daily update complete")

        except Exception as e:
            logger.error(f"Daily update process failed: {e}")
            raise

        return results

    async def _fetch_asx_daily(self) -> int:
        """Fetch ASX daily data - placeholder for actual implementation"""
        # Replace with actual spider service call
        return 42  # Placeholder count

    async def _fetch_vanguard_data(self) -> int:
        """Fetch Vanguard data - placeholder for actual implementation"""
        # Replace with actual spider service call
        return 15  # Placeholder count

    async def _fetch_betashares_data(self) -> int:
        """Fetch BetaShares data - placeholder for actual implementation"""
        # Replace with actual spider service call
        return 8  # Placeholder count

    async def _fetch_single_date(self, source: str):
        """Fetch data for a single date"""
        if self.current_operation and not self.current_operation.done():
            signalBus.infoBarSignal.emit("WARNING", "Operation in Progress",
                                         "Another operation is already running.")
            return

        try:
            date_picker = self.findChild(DatePicker, f"{source}_date")
            if not date_picker:
                return

            target_date = date_picker.date.toPython()

            signalBus.spiderLogSignal.emit(f"Fetching {source} data for {target_date}")

            # Execute single date fetch
            result = await self._execute_single_date_fetch(source, target_date)

            self._handle_fetch_complete(result)

        except Exception as e:
            logger.error(f"Single date fetch failed: {e}")
            self._handle_operation_error(str(e))

    async def _fetch_by_ticker(self, source: str):
        """Fetch data by ticker"""
        if self.current_operation and not self.current_operation.done():
            signalBus.infoBarSignal.emit("WARNING", "Operation in Progress",
                                         "Another operation is already running.")
            return

        try:
            ticker_input = self.findChild(LineEdit, f"{source}_ticker")
            if not ticker_input:
                return

            ticker = ticker_input.text().strip().upper()
            if not ticker:
                signalBus.infoBarSignal.emit("WARNING", "Input Error",
                                             "Please enter a ticker code.")
                return

            signalBus.spiderLogSignal.emit(f"Fetching {source} data for ticker {ticker}")

            # Execute ticker fetch
            result = await self._execute_ticker_fetch(source, ticker)

            self._handle_fetch_complete(result)

        except Exception as e:
            logger.error(f"Ticker fetch failed: {e}")
            self._handle_operation_error(str(e))

    async def _execute_single_date_fetch(self, source: str, target_date) -> Dict[str, Any]:
        """Execute single date fetch"""
        # Placeholder implementation - replace with actual spider service calls
        await asyncio.sleep(0.5)  # Simulate network delay
        count = 5  # Placeholder count
        return {"count": count, "source": source, "date": str(target_date)}

    async def _execute_ticker_fetch(self, source: str, ticker: str) -> Dict[str, Any]:
        """Execute ticker fetch"""
        # Placeholder implementation - replace with actual spider service calls
        await asyncio.sleep(0.5)  # Simulate network delay
        count = 3  # Placeholder count
        return {"count": count, "source": source, "ticker": ticker}

    def _handle_daily_update_complete(self, results: Dict[str, Any]):
        """Handle daily update completion"""
        # Update last update times
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for source in ["asx", "vanguard", "betashares"]:
            self.last_update_times[source] = now
            label = self.findChild(BodyLabel, f"{source}_update_label")
            if label:
                label.setText(f"Last Update: {now}")

        # Show summary
        total = sum(r["count"] for r in results.values())
        errors = sum(len(r["errors"]) for r in results.values())

        if errors > 0:
            signalBus.infoBarSignal.emit("WARNING", "Daily Update Complete",
                                         f"Fetched {total} records with {errors} errors")
        else:
            signalBus.infoBarSignal.emit("SUCCESS", "Daily Update Complete",
                                         f"Successfully fetched {total} records")

    def _handle_fetch_complete(self, result: Dict[str, Any]):
        """Handle single fetch completion"""
        count = result.get("count", 0)
        source = result.get("source", "")

        signalBus.infoBarSignal.emit("SUCCESS", "Fetch Complete",
                                     f"Fetched {count} records from {source}")

    def _handle_operation_error(self, error_message: str):
        """Handle operation error"""
        signalBus.infoBarSignal.emit("ERROR", "Operation Failed", error_message)
        signalBus.spiderLogSignal.emit(f"ERROR: {error_message}")

    def _on_progress(self, value: int, message: str):
        """Handle progress update"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    def _on_log_message(self, message: str):
        """Add message to log output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def refresh(self):
        """Refresh the view"""
        self._load_update_times()
        # Refresh database info
        if hasattr(self, 'db_info_table'):
            self._populate_db_info(self.db_info_table)
        signalBus.infoBarSignal.emit("SUCCESS", "Refresh Complete", "Spider view refreshed")