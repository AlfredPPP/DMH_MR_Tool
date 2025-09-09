# src/dmh_mr_tool/ui/views/spider_view.py
"""Spider Interface for fetching and managing announcement data"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QPushButton
)
from qfluentwidgets import (
    LineEdit, ComboBox, PushButton, PrimaryPushButton,
    ProgressRing, TableWidget, CardWidget, StrongBodyLabel,
    BodyLabel, CaptionLabel, InfoBar, InfoBarPosition,
    SpinBox, FluentIcon as FIF, IndeterminateProgressRing
)
from qasync import asyncSlot

from ..views.base_view import BaseInterface, SeparatorWidget
from ui.utils.signal_bus import signalBus
from ui.utils.infobar import raise_error_bar_in_class
from business.services.spider_service import SpiderService
from database.connection import DatabaseManager
from database.repositories.asx_repository import AsxInfoRepository
from database.models import AsxInfo
from config.settings import CONFIG
from core.utils import USERNAME

import structlog

logger = structlog.get_logger()


class DataSourceCard(CardWidget):
    """Card widget showing data source status"""

    def __init__(self, source_name: str, parent=None):
        super().__init__(parent)
        self.source_name = source_name
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Source name
        self.nameLabel = StrongBodyLabel(self.source_name, self)
        layout.addWidget(self.nameLabel)

        # Last update time
        self.updateTimeLabel = BodyLabel("Last Update: -", self)
        layout.addWidget(self.updateTimeLabel)

        # Record count
        self.countLabel = CaptionLabel("Records: 0", self)
        layout.addWidget(self.countLabel)

        self.setFixedHeight(100)

    def updateStatus(self, last_update: Optional[datetime], count: int):
        """Update the card with latest status"""
        if last_update:
            time_str = last_update.strftime("%Y-%m-%d %H:%M:%S")
            self.updateTimeLabel.setText(f"Last Update: {time_str}")
        else:
            self.updateTimeLabel.setText("Last Update: Never")
        self.countLabel.setText(f"Records: {count:,}")


class SpiderInterface(BaseInterface):
    """Spider Interface for data fetching operations"""

    def __init__(self, parent=None):
        super().__init__(
            title="Spider",
            subtitle="Fetch and manage announcement data from various sources",
            parent=parent
        )
        self.setObjectName('dbBrowserInterface')
        self.db_manager = None
        self.spider_service = None
        self.initUI()
        self.initDatabase()
        self.connectSignalToSlot()

        # Auto refresh status on load
        QTimer.singleShot(100, self.refreshDataSourceStatus)

    def initDatabase(self):
        """Initialize database manager and spider service"""
        self.db_manager = DatabaseManager(CONFIG.database)
        self.db_manager.initialize()
        self.spider_service = SpiderService(self.db_manager)

    def initUI(self):
        """Initialize the user interface"""
        # UI body
        self.body_layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(self.body_layout)

        # Data source status cards
        self.addDataSourceStatus()

        # ASX daily data fetch
        self.addDailyDataFetch()

        # ASX specific ticker fetch
        self.addSpecificTickerFetch()

        # Batch update section
        self.addBatchUpdate()

        # Activity log
        self.addActivityLog()

        self.addPageBody("", widget, stretch=1)

    def addDataSourceStatus(self):
        """Add data source status cards"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(16)

        # Create status cards for each data source
        self.asxCard = DataSourceCard("ASX", widget)
        self.vanguardCard = DataSourceCard("Vanguard", widget)
        self.betasharesCard = DataSourceCard("BetaShares", widget)
        self.isharesCard = DataSourceCard("iShares (TBD)", widget)

        layout.addWidget(self.asxCard)
        layout.addWidget(self.vanguardCard)
        layout.addWidget(self.betasharesCard)
        layout.addWidget(self.isharesCard)
        layout.addStretch()

        title = StrongBodyLabel("Data Source Status")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addDailyDataFetch(self):
        """Add daily data fetch section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # Date selection
        self.dailyComboBox = ComboBox(widget)
        self.dailyComboBox.addItems(["Today", "Previous Business Day"])
        self.dailyComboBox.setCurrentIndex(1)  # Default to previous day

        # Fetch button
        self.dailyFetchBtn = PrimaryPushButton("Fetch Daily Data", widget)
        self.dailyFetchBtn.setIcon(FIF.DOWNLOAD)
        self.dailyFetchBtn.clicked.connect(self.onDailyFetch)

        # Progress indicator
        self.dailyProgress = ProgressRing(widget)
        self.dailyProgress.setFixedSize(24, 24)
        self.dailyProgress.setVisible(False)

        layout.addWidget(BodyLabel("ASX Daily Data:", widget))
        layout.addWidget(self.dailyComboBox)
        layout.addWidget(self.dailyFetchBtn)
        layout.addWidget(self.dailyProgress)
        layout.addStretch()

        title = StrongBodyLabel("Fetch Daily Announcements")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addSpecificTickerFetch(self):
        """Add specific ticker fetch section"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)

        # ASX code input
        self.asxCodeEdit = LineEdit(widget)
        self.asxCodeEdit.setPlaceholderText("Enter ASX Code (e.g., FLO)")
        self.asxCodeEdit.setFixedWidth(200)

        # Year selection
        current_year = datetime.now().year
        self.yearSpinBox = SpinBox(widget)
        self.yearSpinBox.setRange(2020, current_year + 1)
        self.yearSpinBox.setValue(current_year)

        # Fetch button
        self.tickerFetchBtn = PrimaryPushButton("Fetch Ticker Data", widget)
        self.tickerFetchBtn.setIcon(FIF.SEARCH)
        self.tickerFetchBtn.clicked.connect(self.onTickerFetch)

        # Progress indicator
        self.tickerProgress = IndeterminateProgressRing(widget)
        self.tickerProgress.setFixedSize(24, 24)
        self.tickerProgress.setVisible(False)

        layout.addWidget(BodyLabel("ASX Code:", widget))
        layout.addWidget(self.asxCodeEdit)
        layout.addWidget(BodyLabel("Year:", widget))
        layout.addWidget(self.yearSpinBox)
        layout.addWidget(self.tickerFetchBtn)
        layout.addWidget(self.tickerProgress)
        layout.addStretch()

        title = StrongBodyLabel("Fetch Specific Ticker Announcements")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addBatchUpdate(self):
        """Add batch update section"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Batch controls
        controlLayout = QHBoxLayout()

        self.batchUpdateBtn = PrimaryPushButton("Run Daily Spider", widget)
        self.batchUpdateBtn.setIcon(FIF.SYNC)
        self.batchUpdateBtn.clicked.connect(self.onBatchUpdate)

        self.syncUrlBtn = PushButton("Sync PDF URLs", widget)
        self.syncUrlBtn.setIcon(FIF.LINK)
        self.syncUrlBtn.clicked.connect(self.onSyncUrls)

        self.batchProgress = ProgressRing(widget)
        self.batchProgress.setFixedSize(24, 24)
        self.batchProgress.setVisible(False)

        controlLayout.addWidget(self.batchUpdateBtn)
        controlLayout.addWidget(self.syncUrlBtn)
        controlLayout.addWidget(self.batchProgress)
        controlLayout.addStretch()

        # Status label
        self.batchStatusLabel = CaptionLabel("Ready to update all data sources", widget)

        layout.addLayout(controlLayout)
        layout.addWidget(self.batchStatusLabel)

        title = StrongBodyLabel("Batch Operations")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)
        self.body_layout.addWidget(SeparatorWidget(self))

    def addActivityLog(self):
        """Add activity log section"""
        self.logTextEdit = QTextEdit()
        self.logTextEdit.setReadOnly(True)
        self.logTextEdit.setMaximumHeight(200)
        self.logTextEdit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        # Clear log button
        widget = QWidget()
        layout = QVBoxLayout(widget)

        clearBtn = PushButton("Clear Log", widget)
        clearBtn.setIcon(FIF.DELETE)
        clearBtn.clicked.connect(self.logTextEdit.clear)

        layout.addWidget(self.logTextEdit)
        layout.addWidget(clearBtn, alignment=Qt.AlignmentFlag.AlignRight)

        title = StrongBodyLabel("Activity Log")
        self.body_layout.addWidget(title)
        self.body_layout.addWidget(widget)

    def connectSignalToSlot(self):
        """Connect signals to slots"""
        # Connect to signal bus for cross-component communication
        if hasattr(signalBus, 'spiderProgressSignal'):
            signalBus.spiderProgressSignal.connect(self.updateProgress)

    def logActivity(self, message: str, level: str = "INFO"):
        """Log activity to the log widget"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": "#d4d4d4",
            "SUCCESS": "#4ec9b0",
            "WARNING": "#ce9178",
            "ERROR": "#f48771"
        }
        color = color_map.get(level, "#d4d4d4")

        html = f'<span style="color: #808080">[{timestamp}]</span> <span style="color: {color}">{message}</span>'
        self.logTextEdit.append(html)

        # Auto scroll to bottom
        scrollbar = self.logTextEdit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @asyncSlot()
    @raise_error_bar_in_class
    async def onDailyFetch(self):
        """Handle daily data fetch"""
        try:
            self.dailyFetchBtn.setEnabled(False)
            self.dailyProgress.setVisible(True)

            is_today = self.dailyComboBox.currentIndex() == 0
            date_str = "today" if is_today else "previous business day"

            self.logActivity(f"Fetching ASX announcements for {date_str}...")

            # Fetch announcements
            from spiders.asx_spider import AsxSpider
            spider = AsxSpider()
            announcements = await spider.fetch_announcements_by_day(is_today)

            if not announcements:
                self.logActivity(f"No announcements found for {date_str}", "WARNING")
                signalBus.infoBarSignal.emit("WARNING", "No Data", f"No announcements found for {date_str}")
                return

            # Save to database
            saved_count = 0
            duplicate_count = 0

            with self.db_manager.session() as session:
                repo = AsxInfoRepository(session)

                for item in announcements:
                    if not repo.find_duplicate(item["asx_code"], item["title"], item["pub_date"]):
                        repo.create(
                            asx_code=item["asx_code"],
                            title=item["title"],
                            pub_date=item["pub_date"],
                            pdf_mask_url=item["pdf_mask_url"],
                            page_num=item["page_num"],
                            file_size=item["file_size"],
                            update_user=USERNAME
                        )
                        saved_count += 1
                    else:
                        duplicate_count += 1

            self.logActivity(
                f"Fetched {len(announcements)} announcements: {saved_count} new, {duplicate_count} duplicates",
                "SUCCESS")
            signalBus.infoBarSignal.emit("SUCCESS", "Fetch Complete",
                                         f"Saved {saved_count} new announcements, skipped {duplicate_count} duplicates")

            # Refresh status
            self.refreshDataSourceStatus()

        except Exception as e:
            self.logActivity(f"Error fetching daily data: {str(e)}", "ERROR")
            raise
        finally:
            self.dailyFetchBtn.setEnabled(True)
            self.dailyProgress.setVisible(False)

    @asyncSlot()
    @raise_error_bar_in_class
    async def onTickerFetch(self):
        """Handle specific ticker fetch"""
        try:
            asx_code = self.asxCodeEdit.text().strip().upper()
            year = str(self.yearSpinBox.value())

            if not asx_code:
                signalBus.infoBarSignal.emit("WARNING", "Input Required", "Please enter an ASX code")
                return

            self.tickerFetchBtn.setEnabled(False)
            self.tickerProgress.setVisible(True)

            self.logActivity(f"Fetching announcements for {asx_code} in {year}...")

            # Fetch announcements
            await self.spider_service.crawl_asx_info([asx_code], year)

            # Count results
            with self.db_manager.session() as session:
                repo = AsxInfoRepository(session)
                count = len(repo.get_by_asx_code(asx_code))

            self.logActivity(f"Successfully fetched announcements for {asx_code}", "SUCCESS")
            signalBus.infoBarSignal.emit("SUCCESS", "Fetch Complete",
                                         f"Fetched announcements for {asx_code} ({count} total records)")

            # Refresh status
            self.refreshDataSourceStatus()

        except Exception as e:
            self.logActivity(f"Error fetching ticker data: {str(e)}", "ERROR")
            raise
        finally:
            self.tickerFetchBtn.setEnabled(True)
            self.tickerProgress.setVisible(False)

    @asyncSlot()
    @raise_error_bar_in_class
    async def onBatchUpdate(self):
        """Handle batch update for all sources"""
        try:
            self.batchUpdateBtn.setEnabled(False)
            self.batchProgress.setVisible(True)
            self.batchStatusLabel.setText("Running daily spider process...")

            self.logActivity("Starting daily spider process...")

            # Fetch previous business day ASX data
            self.logActivity("Fetching ASX previous business day announcements...")
            from spiders.asx_spider import AsxSpider
            spider = AsxSpider()
            announcements = await spider.fetch_announcements_by_day(is_today=False)

            saved_count = 0
            duplicate_count = 0
            with self.db_manager.session() as session:
                repo = AsxInfoRepository(session)
                for item in announcements:
                    # Ensure pub_date is a date object
                    pub_date = item["pub_date"]
                    if isinstance(pub_date, datetime):
                        pub_date = pub_date.date()

                    record, is_new = repo.create_if_not_exists(
                        asx_code=item["asx_code"],
                        title=item["title"],
                        pub_date=pub_date,
                        pdf_mask_url=item.get("pdf_mask_url"),
                        page_num=item.get("page_num", 0),
                        file_size=item.get("file_size", ""),
                        update_user=USERNAME
                    )

                    if is_new:
                        saved_count += 1
                    else:
                        duplicate_count += 1

            self.logActivity(f"ASX: Saved {saved_count} new announcements, {duplicate_count} duplicates", "SUCCESS")

            # TODO: Add Vanguard, BetaShares, iShares updates here
            self.logActivity("Vanguard update: Not implemented yet", "WARNING")
            self.logActivity("BetaShares update: Not implemented yet", "WARNING")

            self.batchStatusLabel.setText("Daily spider process completed")
            self.logActivity("Daily spider process completed successfully", "SUCCESS")
            signalBus.infoBarSignal.emit("SUCCESS", "Update Complete", "Daily spider process completed successfully")

            # Refresh status
            self.refreshDataSourceStatus()

        except Exception as e:
            self.batchStatusLabel.setText("Daily spider process failed")
            self.logActivity(f"Error in batch update: {str(e)}", "ERROR")
            raise
        finally:
            self.batchUpdateBtn.setEnabled(True)
            self.batchProgress.setVisible(False)

    @asyncSlot()
    @raise_error_bar_in_class
    async def onSyncUrls(self):
        """Sync PDF URLs for announcements"""
        try:
            self.syncUrlBtn.setEnabled(False)
            self.batchProgress.setVisible(True)

            self.logActivity("Syncing PDF URLs...")

            # Get announcements that need URL sync
            with self.db_manager.session() as session:
                repo = AsxInfoRepository(session)
                records = session.query(AsxInfo).filter(
                    AsxInfo.pdf_mask_url.isnot(None),
                    AsxInfo.pdf_url.is_(None)
                ).limit(20).all()  # Limit to prevent overwhelming

                asx_codes = list(set([r.asx_code for r in records]))

            if not asx_codes:
                self.logActivity("No URLs to sync", "INFO")
                signalBus.infoBarSignal.emit("INFO", "No URLs to Sync", "All PDF URLs are already synced")
                return

            self.logActivity(f"Syncing URLs for {len(records)} announcements...")

            # Sync URLs
            await self.spider_service.sync_asx_act_url(asx_codes)

            self.logActivity(f"Successfully synced {len(records)} PDF URLs", "SUCCESS")
            signalBus.infoBarSignal.emit("SUCCESS", "Sync Complete", f"Synced {len(records)} PDF URLs")

        except Exception as e:
            self.logActivity(f"Error syncing URLs: {str(e)}", "ERROR")
            raise
        finally:
            self.syncUrlBtn.setEnabled(True)
            self.batchProgress.setVisible(False)

    def refreshDataSourceStatus(self):
        """Refresh data source status cards"""
        try:
            with self.db_manager.session() as session:
                repo = AsxInfoRepository(session)

                # Get ASX status
                asx_count = repo.count()
                asx_latest = session.query(AsxInfo.update_timestamp) \
                    .order_by(AsxInfo.update_timestamp.desc()) \
                    .first()

                self.asxCard.updateStatus(
                    asx_latest[0] if asx_latest else None,
                    asx_count
                )

                # TODO: Update other cards when their repositories are implemented
                self.vanguardCard.updateStatus(None, 0)
                self.betasharesCard.updateStatus(None, 0)
                self.isharesCard.updateStatus(None, 0)

        except Exception as e:
            logger.error(f"Error refreshing status: {e}")

    def updateProgress(self, source: str, current: int, total: int):
        """Update progress for ongoing operations"""
        percent = int((current / total) * 100) if total > 0 else 0
        self.logActivity(f"{source}: {current}/{total} ({percent}%)", "INFO")

    def closeEvent(self, event):
        """Clean up resources on close"""
        if self.db_manager:
            self.db_manager.close()
        super().closeEvent(event)