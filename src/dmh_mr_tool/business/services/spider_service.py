# src/dmh_mr_tool/business/services/spider_service.py
"""Spider service for managing web crawling operations"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from spiders.asx_spider import AsxSpider
from database.connection import DatabaseManager
from database.repositories.asx_repository import AsxInfoRepository
from database.models import AsxInfo, DownloadStatus
from config.settings import CONFIG
from core.utils import USERNAME
from ui.utils.signal_bus import signalBus

import structlog

logger = structlog.get_logger()


class SpiderService:
    """Service for managing spider operations and data fetching"""

    _instance = None
    _db_manager = None

    def __new__(cls):
        """Singleton pattern for service"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize service with database manager"""
        if not self._initialized:
            self._ensure_db_manager()
            self.asx_spider = AsxSpider()
            # TODO: Initialize other spiders when implemented
            # self.vanguard_spider = VanguardSpider()
            # self.betashares_spider = BetaSharesSpider()
            # self.ishares_spider = ISharesSpider()
            self._initialized = True

    def _ensure_db_manager(self):
        """Ensure database manager is initialized"""
        if SpiderService._db_manager is None:
            SpiderService._db_manager = DatabaseManager(CONFIG.database)
            SpiderService._db_manager.initialize()

    @property
    def db_manager(self):
        """Get database manager instance"""
        return SpiderService._db_manager

    async def crawl_asx_info(self, asx_codes: List[str], year: str) -> Dict[str, int]:
        """
        Crawl ASX announcements for specified codes and year

        Args:
            asx_codes: List of ASX ticker codes
            year: Year to fetch announcements for

        Returns:
            Dictionary with saved, duplicates, and total counts
        """
        # Fetch data from spider
        tasks = [self.asx_spider.fetch_announcements_by_code(code, year) for code in asx_codes]
        raw_data_lists = await asyncio.gather(*tasks)

        # Flatten the list of lists
        all_announcements = []
        for data_list in raw_data_lists:
            all_announcements.extend(data_list)

        # Save to database
        return await self._save_announcements(all_announcements, f"ASX crawl for {asx_codes} in {year}")

    async def fetch_daily_announcements(self, is_today: bool = False) -> Dict[str, int]:
        """
        Fetch daily announcements from ASX

        Args:
            is_today: If True, fetch today's announcements, else previous business day

        Returns:
            Dictionary with saved, duplicates, and total counts
        """
        announcements = await self.asx_spider.fetch_announcements_by_day(is_today)
        return await self._save_announcements(
            announcements,
            f"Daily fetch ({'today' if is_today else 'previous business day'})"
        )

    async def sync_pdf_urls(self, limit: int = 20) -> int:
        """
        Sync actual PDF URLs for announcements with mask URLs

        Args:
            limit: Maximum number of URLs to sync in one batch

        Returns:
            Number of URLs synced
        """
        synced_count = 0

        with self.db_manager.session() as session:
            repo = AsxInfoRepository(session)

            # Get records that need URL sync
            records = session.query(AsxInfo).filter(
                AsxInfo.pdf_mask_url.isnot(None),
                AsxInfo.pdf_url.is_(None),
            ).limit(limit).all()

            if not records:
                logger.info("No URLs to sync")
                return 0

            # Get ASX codes for these records
            asx_codes = list(set([r.asx_code for r in records]))

            # Process records
            total = len(records)
            for i, record in enumerate(records):
                try:
                    # Get actual PDF URL
                    pdf_url = await self.asx_spider.get_pdf_actual_url(record.pdf_mask_url)
                    repo.update(record.id, pdf_url=pdf_url, update_user=USERNAME)
                    synced_count += 1

                    # Emit progress signal
                    if hasattr(signalBus, 'spiderProgressSignal'):
                        signalBus.spiderProgressSignal.emit("URL Sync", i + 1, total)

                    logger.debug(f"URL synced", asx_code=record.asx_code, id=record.id)

                except Exception as e:
                    logger.error(f"Failed to sync URL",
                                 asx_code=record.asx_code,
                                 id=record.id,
                                 error=str(e))
                    # Continue with next record

            session.commit()

        logger.info(f"URL sync complete", synced=synced_count, codes=asx_codes)
        return synced_count

    async def download_pdf(self, info_id: int, save_path: str) -> bool:
        """
        Download PDF for a specific announcement

        Args:
            info_id: ID of the announcement
            save_path: Path to save the PDF

        Returns:
            True if successful, False otherwise
        """
        with self.db_manager.session() as session:
            repo = AsxInfoRepository(session)
            info = repo.get_by_id(info_id)

            if not info:
                logger.error(f"Announcement not found", id=info_id)
                return False

            # Ensure we have the actual PDF URL
            if not info.pdf_url:
                if info.pdf_mask_url:
                    try:
                        info.pdf_url = await self.asx_spider.get_pdf_actual_url(info.pdf_mask_url)
                        repo.update(info.id, pdf_url=info.pdf_url, update_user=USERNAME)
                    except Exception as e:
                        logger.error(f"Failed to get PDF URL", id=info_id, error=str(e))
                        return False
                else:
                    logger.error(f"No PDF URL available", id=info_id)
                    return False

            # Download the PDF
            try:
                await self.asx_spider.download_pdf(info.pdf_url, save_path)
                repo.mark_downloaded(info.id, DownloadStatus.DOWNLOADED)
                logger.info(f"PDF downloaded", id=info_id, path=save_path)
                return True
            except Exception as e:
                logger.error(f"Failed to download PDF", id=info_id, error=str(e))
                repo.mark_downloaded(info.id, DownloadStatus.FAILED)
                return False

    async def run_daily_spider(self) -> Dict[str, Dict[str, int]]:
        """
        Run the complete daily spider process for all sources

        Returns:
            Dictionary with results from all sources
        """
        results = {
            "asx": {},
            "vanguard": {},
            "betashares": {},
            "ishares": {}
        }

        # ASX - Previous business day
        logger.info("Starting daily ASX spider")
        try:
            results["asx"] = await self.fetch_daily_announcements(is_today=False)
        except Exception as e:
            logger.error(f"ASX daily spider failed", error=str(e))
            results["asx"] = {"error": str(e)}

        # TODO: Implement other spiders
        # try:
        #     results["vanguard"] = await self.fetch_vanguard_data()
        # except Exception as e:
        #     logger.error(f"Vanguard spider failed", error=str(e))
        #     results["vanguard"] = {"error": str(e)}

        logger.info("Daily spider complete", results=results)
        return results

    def get_data_source_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all data sources

        Returns:
            Dictionary with status for each source including last_update and count
        """
        status = {
            "asx": {"last_update": None, "count": 0},
            "vanguard": {"last_update": None, "count": 0},
            "betashares": {"last_update": None, "count": 0},
            "ishares": {"last_update": None, "count": 0}
        }

        with self.db_manager.session() as session:
            # ASX status
            repo = AsxInfoRepository(session)
            status["asx"]["count"] = repo.count()

            latest = session.query(AsxInfo.update_timestamp) \
                .order_by(AsxInfo.update_timestamp.desc()) \
                .first()
            if latest:
                status["asx"]["last_update"] = latest[0]

            # TODO: Add other data source status queries
            # vanguard_repo = VanguardRepository(session)
            # status["vanguard"]["count"] = vanguard_repo.count()
            # ...

        return status

    def get_announcements_by_criteria(
            self,
            asx_code: Optional[str] = None,
            start_date: Optional[date] = None,
            end_date: Optional[date] = None,
            download_status: Optional[DownloadStatus] = None,
            limit: Optional[int] = None
    ) -> List[AsxInfo]:
        """
        Get announcements by various criteria

        Args:
            asx_code: Optional ASX code filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            download_status: Optional download status filter
            limit: Optional limit on results

        Returns:
            List of matching announcements
        """
        with self.db_manager.session() as session:
            query = session.query(AsxInfo)

            if asx_code:
                query = query.filter(AsxInfo.asx_code == asx_code.upper())
            if start_date:
                query = query.filter(AsxInfo.pub_date >= start_date)
            if end_date:
                query = query.filter(AsxInfo.pub_date <= end_date)
            if download_status is not None:
                query = query.filter(AsxInfo.downloaded == download_status)

            query = query.order_by(AsxInfo.pub_date.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

    async def _save_announcements(self, announcements: List[Dict], operation_name: str) -> Dict[str, int]:
        """
        Internal method to save announcements to database

        Args:
            announcements: List of announcement dictionaries
            operation_name: Name of the operation for logging

        Returns:
            Dictionary with saved, duplicates, and total counts
        """
        saved_count = 0
        duplicate_count = 0

        with self.db_manager.session() as session:
            repo = AsxInfoRepository(session)

            for item in announcements:
                # Ensure pub_date is a date object
                pub_date = item["pub_date"]
                if isinstance(pub_date, datetime):
                    pub_date = pub_date.date()

                # Check for duplicate and create if not exists
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

        logger.info(f"{operation_name} complete",
                    saved=saved_count,
                    duplicates=duplicate_count,
                    total=len(announcements))

        return {
            "saved": saved_count,
            "duplicates": duplicate_count,
            "total": len(announcements)
        }

    def close(self):
        """Close database connections when service is destroyed"""
        if self.db_manager:
            self.db_manager.close()