# Addition to src/dmh_mr_tool/database/repositories/asx_repository.py
"""Repository for ASX data operations - Enhanced version"""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from ..models import AsxInfo, AsxNzData, DownloadStatus
from .base import BaseRepository


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
        """Check if announcement already exists"""
        return self.session.query(AsxInfo).filter(
            and_(
                AsxInfo.asx_code == asx_code,
                AsxInfo.title == title,
                AsxInfo.pub_date == pub_date
            )
        ).first()


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
