# src/dmh_mr_tool/database/repositories/asx_repository.py
"""Repository for ASX data operations - Fixed version"""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from ..models import AsxInfo, AsxNzData, DownloadStatus, ParseStatus
from .base import BaseRepository

import structlog

logger = structlog.get_logger()


class AsxInfoRepository(BaseRepository[AsxInfo]):
    """Repository for ASX announcement information"""

    def __init__(self, session: Session):
        super().__init__(session, AsxInfo)

    def get_by_asx_code(self, asx_code: str,
                        start_date: Optional[date] = None,
                        end_date: Optional[date] = None) -> List[AsxInfo]:
        """Get announcements by ASX code within date range"""
        query = self.session.query(AsxInfo).filter(
            AsxInfo.asx_code == asx_code
        )

        if start_date:
            query = query.filter(AsxInfo.pub_date >= start_date)
        if end_date:
            query = query.filter(AsxInfo.pub_date <= end_date)

        return query.order_by(AsxInfo.pub_date.desc()).all()

    def get_by_date_range(self, start_date: date, end_date: date) -> List[AsxInfo]:
        """Get announcements within date range"""
        return self.session.query(AsxInfo).filter(
            and_(
                AsxInfo.pub_date >= start_date,
                AsxInfo.pub_date <= end_date
            )
        ).order_by(AsxInfo.pub_date.desc()).all()

    def get_undownloaded(self, limit: int = None) -> List[AsxInfo]:
        """Get announcements that haven't been downloaded"""
        query = self.session.query(AsxInfo).filter(
            AsxInfo.downloaded == DownloadStatus.NOT_DOWNLOADED
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def count(self) -> int:
        """Get total count of ASX info records"""
        return self.session.query(func.count(AsxInfo.id)).scalar()

    def mark_downloaded(self, id: int, status: DownloadStatus = DownloadStatus.DOWNLOADED) -> bool:
        """Mark announcement as downloaded"""
        return self.update(id, downloaded=status) is not None

    def find_duplicate(self, asx_code: str, title: str, pub_date: date) -> Optional[AsxInfo]:
        """
        Check if announcement already exists

        Args:
            asx_code: ASX ticker code
            title: Announcement title
            pub_date: Publication date

        Returns:
            Existing record if found, None otherwise
        """
        # Ensure pub_date is a date object
        if isinstance(pub_date, datetime):
            pub_date = pub_date.date()

        # Clean the inputs
        asx_code = asx_code.strip().upper() if asx_code else ""
        title = title.strip() if title else ""

        logger.debug(f"Checking for duplicate",
                     asx_code=asx_code,
                     title=title[:50],
                     pub_date=pub_date)

        existing = self.session.query(AsxInfo).filter(
            and_(
                AsxInfo.asx_code == asx_code,
                AsxInfo.title == title,
                AsxInfo.pub_date == pub_date
            )
        ).first()

        if existing:
            logger.debug(f"Found duplicate announcement",
                         id=existing.id,
                         asx_code=asx_code)

        return existing

    def create_if_not_exists(self, **kwargs) -> tuple[Optional[AsxInfo], bool]:
        """
        Create announcement if it doesn't exist

        Returns:
            Tuple of (record, is_new) where is_new indicates if a new record was created
        """
        # Extract key fields for duplicate check
        asx_code = kwargs.get('asx_code', '').strip().upper()
        title = kwargs.get('title', '').strip()
        pub_date = kwargs.get('pub_date')

        # Ensure pub_date is a date object
        if isinstance(pub_date, datetime):
            pub_date = pub_date.date()

        # Check for existing record
        existing = self.find_duplicate(asx_code, title, pub_date)

        if existing:
            return existing, False

        # Create new record
        # Update kwargs with cleaned values
        kwargs['asx_code'] = asx_code
        kwargs['title'] = title
        kwargs['pub_date'] = pub_date

        new_record = self.create(**kwargs)
        return new_record, True


class AsxNzDataRepository(BaseRepository[AsxNzData]):
    """Repository for ASX/NZ parsed data"""

    def __init__(self, session: Session):
        super().__init__(session, AsxNzData)

    def get_by_asset_id(self, asset_id: str,
                        ex_date: Optional[date] = None) -> List[AsxNzData]:
        """Get data by asset ID and optional ex-date"""
        query = self.session.query(AsxNzData).filter(
            AsxNzData.asset_id == asset_id
        )

        if ex_date:
            query = query.filter(AsxNzData.ex_date == ex_date)

        return query.all()

    def get_by_info_id(self, info_id: int) -> List[AsxNzData]:
        """Get all parsed data for an announcement"""
        return self.session.query(AsxNzData).filter(
            AsxNzData.info_id == info_id
        ).all()

    def get_recent_updates(self, days: int = 7) -> List[AsxNzData]:
        """Get recently updated data"""
        from datetime import timedelta
        cutoff_date = datetime.now().date() - timedelta(days=days)

        return self.session.query(AsxNzData).join(
            AsxInfo
        ).filter(
            AsxInfo.update_timestamp >= cutoff_date
        ).all()

    def count(self) -> int:
        """Get total count of ASX NZ data records"""
        return self.session.query(func.count(AsxNzData.id)).scalar()