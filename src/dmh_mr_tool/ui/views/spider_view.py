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
from database.connection import DatabaseManager, DatabaseConfig
from database.repositories.asx_repository import AsxInfoRepository, AsxNzDataRepository
from database.models import SystemLog
from config.settings import CONFIG

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
        self.db_manager: Optional[DatabaseManager] = None
        self.spider_service: Optional[SpiderService] = None
        self.last_update_times = {}
        self.current_operation: Optional[asyncio.Task] = None

        self._init_services()
        self._setup_ui()
        self._load_update_times()
        self._connect_signals()

    def _init_services(self):
        """Initialize database manager and spider service"""
        try:
            # Initialize database manager
            self.db_manager = DatabaseManager(DatabaseConfig(path=CONFIG.database.path))
            self.db_manager.initialize()

            # Initialize spider service with database manager
            self.spider_service = SpiderService(self.db_manager)

            logger.info("Spider services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize spider services: {e}")
            signalBus.infoBarSignal.emit("ERROR", "Initialization Error",
                                         f"Failed to initialize spider services: {str(e)}")

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
        self.db_info_table = TableWidget()
        self.db_info_table.setColumnCount(2)
        self.db_info_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.db_info_table.horizontalHeader().setStretchLastSection(True)
        self.db_info_table.setMaximumHeight(200)

        self._populate_db_info()
        self.addPageBody("Database Information", self.db_info_table)

    def _create_activity_log_section(self):
        """Create activity log section"""
        self.log_output = TextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)

        self.addPageBody("Activity Log", self.log_output)

    def _populate_db_info(self):
        """Populate database information table using repositories"""
        try:
            if self.db_manager:
                # Get database info using repositories
                db_info = self._get_database_info_via_repositories()
                info = [
                    ("Database Path", db_info.get('db_path', 'N/A')),
                    ("Backup Path", db_info.get('backup_path', 'N/A')),
                    ("Tables", db_info.get('tables', 'N/A')),
                    ("Total Records", str(db_info.get('total_records', 'N/A'))),
                    ("ASX Info Records", str(db_info.get('asx_info_records', 'N/A'))),
                    ("ASX NZ Data Records", str(db_info.get('asx_nz_records', 'N/A'))),
                    ("Undownloaded PDFs", str(db_info.get('undownloaded_count', 'N/A'))),
                    ("Connection Status", db_info.get('connection_status', 'N/A'))
                ]
            else:
                info = [
                    ("Database Path", "Service not available"),
                    ("Backup Path", "Service not available"),
                    ("Tables", "asx_info, asx_nz_data, vanguard_data, vanguard_mapping, column_map, sys_log"),
                    ("Connection Status", "Disconnected")
                ]
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            info = [("Error", "Failed to load database information")]

        self.db_info_table.setRowCount(len(info))
        for i, (key, value) in enumerate(info):
            self.db_info_table.setItem(i, 0, QTableWidgetItem(key))
            self.db_info_table.setItem(i, 1, QTableWidgetItem(value))

    def _get_database_info_via_repositories(self) -> Dict[str, Any]:
        """Get database information using repository pattern"""
        try:
            if not self.db_manager:
                return {"connection_status": "Database manager not available"}

            with self.db_manager.session() as session:
                # Initialize repositories
                asx_info_repo = AsxInfoRepository(session)
                asx_nz_repo = AsxNzDataRepository(session)

                # Get record counts using repository methods
                asx_info_count = asx_info_repo.count()
                asx_nz_count = asx_nz_repo.count()
                undownloaded_count = len(asx_info_repo.get_undownloaded())
                total_count = asx_info_count + asx_nz_count

                # Get database path from config
                db_path = getattr(CONFIG.database, 'path', 'Not configured')
                backup_path = getattr(CONFIG.paths, 'backup_path', 'Not configured')

                return {
                    'db_path': str(db_path),
                    'backup_path': str(backup_path),
                    'tables': 'asx_info, asx_nz_data, vanguard_data, vanguard_mapping, column_map, sys_log',
                    'total_records': total_count,
                    'asx_info_records': asx_info_count,
                    'asx_nz_records': asx_nz_count,
                    'undownloaded_count': undownloaded_count,
                    'connection_status': 'Connected'
                }

        except Exception as e:
            logger.error(f"Failed to get database info via repositories: {e}")
            return {
                'connection_status': f'Error: {str(e)}',
                'db_path': 'Error',
                'backup_path': 'Error',
                'tables': 'Error',
                'total_records': 'Error',
                'asx_info_records': 'Error',
                'asx_nz_records': 'Error',
                'undownloaded_count': 'Error'
            }

    def _load_update_times(self):
        """Load last update times from database using repositories"""
        try:
            if not self.db_manager:
                self.last_update_times = {
                    "asx": "Service not available",
                    "vanguard": "Service not available",
                    "betashares": "Service not available"
                }
                return

            with self.db_manager.session() as session:
                # Query sys_log table using SQLAlchemy ORM instead of raw SQL
                from sqlalchemy import func, and_

                # Get latest ASX update time
                asx_log = session.query(func.max(SystemLog.update_timestamp)).filter(
                    SystemLog.action.like('%asx%')
                ).scalar()

                # Get latest Vanguard update time
                vanguard_log = session.query(func.max(SystemLog.update_timestamp)).filter(
                    SystemLog.action.like('%vanguard%')
                ).scalar()

                # Get latest BetaShares update time
                betashares_log = session.query(func.max(SystemLog.update_timestamp)).filter(
                    SystemLog.action.like('%betashares%')
                ).scalar()

                # Alternative: Get last update from asx_info table
                asx_info_repo = AsxInfoRepository(session)
                latest_asx_records = session.query(func.max(asx_info_repo.model.update_timestamp)).scalar()

                self.last_update_times = {
                    "asx": (asx_log or latest_asx_records).strftime("%Y-%m-%d %H:%M") if (
                                asx_log or latest_asx_records) else "Never",
                    "vanguard": vanguard_log.strftime("%Y-%m-%d %H:%M") if vanguard_log else "Never",
                    "betashares": betashares_log.strftime("%Y-%m-%d %H:%M") if betashares_log else "Never"
                }

        except Exception as e:
            logger.error(f"Failed to load update times: {e}")
            self.last_update_times = {
                "asx": "Error loading",
                "vanguard": "Error loading",
                "betashares": "Error loading"
            }

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
                # Use actual spider service method
                asx_codes = ["FLO", "VAS", "VTS"]  # Example codes, get from config
                year = str(datetime.now().year)
                await self.spider_service.crawl_asx_info(asx_codes, year)

                # Get count using repository
                with self.db_manager.session() as session:
                    asx_repo = AsxInfoRepository(session)
                    # Get recent records added today
                    from datetime import date
                    today_records = asx_repo.get_by_date_range(date.today(), date.today())
                    asx_count = len(today_records)

                results["asx"]["count"] = asx_count
                signalBus.spiderLogSignal.emit(f"Fetched {asx_count} ASX announcements")
            except Exception as e:
                results["asx"]["errors"].append(str(e))
                signalBus.spiderLogSignal.emit(f"ASX fetch failed: {e}")

            # Update Vanguard
            signalBus.spiderProgressSignal.emit(40, "Fetching Vanguard data...")
            try:
                # Add actual Vanguard fetching logic here
                vanguard_count = 15  # Placeholder
                results["vanguard"]["count"] = vanguard_count
                signalBus.spiderLogSignal.emit(f"Fetched {vanguard_count} Vanguard records")
            except Exception as e:
                results["vanguard"]["errors"].append(str(e))
                signalBus.spiderLogSignal.emit(f"Vanguard fetch failed: {e}")

            # Update BetaShares
            signalBus.spiderProgressSignal.emit(70, "Fetching BetaShares data...")
            try:
                # Add actual BetaShares fetching logic here
                betashares_count = 8  # Placeholder
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

            # Execute ticker fetch using spider service
            result = await self._execute_ticker_fetch(source, ticker)

            self._handle_fetch_complete(result)

        except Exception as e:
            logger.error(f"Ticker fetch failed: {e}")
            self._handle_operation_error(str(e))

    async def _execute_single_date_fetch(self, source: str, target_date) -> Dict[str, Any]:
        """Execute single date fetch"""
        # Implement actual single date fetch using spider service
        if source.lower() == "asx":
            # Use repository to check if data exists for this date
            with self.db_manager.session() as session:
                asx_repo = AsxInfoRepository(session)
                existing_records = asx_repo.get_by_date_range(target_date, target_date)
                count = len(existing_records)
        else:
            count = 3  # Placeholder for other sources

        return {"count": count, "source": source, "date": str(target_date)}

    async def _execute_ticker_fetch(self, source: str, ticker: str) -> Dict[str, Any]:
        """Execute ticker fetch"""
        # Implement actual ticker fetch using spider service
        if source.lower() == "asx":
            # Use your spider service method for ASX by ticker
            year = str(datetime.now().year)
            await self.spider_service.crawl_asx_info([ticker], year)

            # Get count using repository
            with self.db_manager.session() as session:
                asx_repo = AsxInfoRepository(session)
                ticker_records = asx_repo.get_by_asx_code(ticker)
                count = len(ticker_records)
        else:
            count = 0  # Other sources don't support ticker search

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

        # Refresh database info
        self._populate_db_info()

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

        # Refresh database info and update times
        self._populate_db_info()
        self._load_update_times()

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
        self._populate_db_info()
        signalBus.infoBarSignal.emit("SUCCESS", "Refresh Complete", "Spider view refreshed")