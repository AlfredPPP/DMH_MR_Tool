# src/dmh_mr_tool/business/services/spider_service.py
"""Spider service for managing web crawling operations"""

import asyncio
from typing import List, Optional
from datetime import datetime

from spiders.asx_spider import AsxSpider
from database.connection import DatabaseManager
from database.repositories.asx_repository import AsxInfoRepository
from database.models import AsxInfo
from core.utils import USERNAME
from ui.utils.signal_bus import signalBus

import structlog

logger = structlog.get_logger()


class SpiderService:
    """Service for managing spider operations and data fetching"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.asx_spider = AsxSpider()

    async def crawl_asx_info(self, asx_codes: List[str], year: str) -> dict:
        """
        Crawl ASX announcements for specified codes and year

        Args:
            asx_codes: List of ASX ticker codes
            year: Year to fetch announcements for

        Returns:
            Dictionary with saved and duplicate counts
        """
        tasks = []
        for asx_code in asx_codes:
            tasks.append(self.asx_spider.fetch_announcements_by_code(asx_code, year))

        raw_datas = await asyncio.gather(*tasks)

        saved_count = 0
        duplicate_count = 0

        with self.db_manager.session() as session:
            repo = AsxInfoRepository(session)

            for raw_data in raw_datas:
                for item in raw_data:
                    # Check for duplicates
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

        logger.info(f"ASX crawl complete",
                    saved=saved_count,
                    duplicates=duplicate_count,
                    codes=asx_codes,
                    year=year)

        return {
            "saved": saved_count,
            "duplicates": duplicate_count,
            "total": saved_count + duplicate_count
        }

    async def sync_asx_act_url(self, asx_codes: List[str]) -> int:
        """
        Sync actual PDF URLs for announcements with mask URLs

        Args:
            asx_codes: List of ASX codes to sync URLs for

        Returns:
            Number of URLs synced
        """
        synced_count = 0

        with self.db_manager.session() as session:
            repo = AsxInfoRepository(session)

            # Get records that need URL sync
            records = session.query(AsxInfo).filter(
                AsxInfo.asx_code.in_(asx_codes),
                AsxInfo.pdf_mask_url.isnot(None),
                AsxInfo.pdf_url.is_(None),
            ).all()

            if not records:
                logger.info("No URLs to sync", codes=asx_codes)
                return 0

            # Process records in batches to avoid overwhelming the server
            tasks = []
            for record in records:
                tasks.append(self._process_record(session, repo, record))

            # Emit progress signal if available
            total = len(tasks)
            for i, task in enumerate(tasks):
                await task
                synced_count += 1
                if hasattr(signalBus, 'spiderProgressSignal'):
                    signalBus.spiderProgressSignal.emit("URL Sync", i + 1, total)

            session.commit()

        logger.info(f"URL sync complete", synced=synced_count, codes=asx_codes)
        return synced_count

    async def _process_record(self, session, repo, record):
        """
        Process a single record to get actual PDF URL

        Args:
            session: Database session
            repo: ASX repository instance
            record: ASX info record to process
        """
        try:
            result = await self.asx_spider.get_pdf_actual_url(record.pdf_mask_url)
            repo.update(record.id, pdf_url=result, update_user=USERNAME)
            logger.debug(f"URL synced", asx_code=record.asx_code, id=record.id)
        except Exception as e:
            logger.error(f"Failed to sync URL",
                         asx_code=record.asx_code,
                         id=record.id,
                         error=str(e))
            raise

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
                    # Try to get the actual URL
                    try:
                        info.pdf_url = await self.asx_spider.get_pdf_actual_url(info.pdf_mask_url)
                        repo.update(info.id, pdf_url=info.pdf_url)
                    except Exception as e:
                        logger.error(f"Failed to get PDF URL", id=info_id, error=str(e))
                        return False
                else:
                    logger.error(f"No PDF URL available", id=info_id)
                    return False

            # Download the PDF
            try:
                await self.asx_spider.download_pdf(info.pdf_url, save_path)
                repo.mark_downloaded(info.id)
                logger.info(f"PDF downloaded", id=info_id, path=save_path)
                return True
            except Exception as e:
                logger.error(f"Failed to download PDF", id=info_id, error=str(e))
                repo.mark_downloaded(info.id, status=2)  # Mark as failed
                return False

    async def fetch_daily_announcements(self, is_today: bool = False) -> dict:
        """
        Fetch daily announcements from ASX

        Args:
            is_today: If True, fetch today's announcements, else previous business day

        Returns:
            Dictionary with saved and duplicate counts
        """
        announcements = await self.asx_spider.fetch_announcements_by_day(is_today)

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

        logger.info(f"Daily fetch complete",
                    is_today=is_today,
                    saved=saved_count,
                    duplicates=duplicate_count)

        return {
            "saved": saved_count,
            "duplicates": duplicate_count,
            "total": saved_count + duplicate_count
        }

    async def run_daily_spider(self) -> dict:
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
        results["asx"] = await self.fetch_daily_announcements(is_today=False)

        # TODO: Implement Vanguard spider
        # results["vanguard"] = await self.fetch_vanguard_data()

        # TODO: Implement BetaShares spider
        # results["betashares"] = await self.fetch_betashares_data()

        # TODO: Implement iShares spider
        # results["ishares"] = await self.fetch_ishares_data()

        logger.info("Daily spider complete", results=results)
        return results