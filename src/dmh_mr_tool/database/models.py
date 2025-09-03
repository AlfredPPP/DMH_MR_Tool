# src/dmh_mr_tool/database/models.py
"""SQLAlchemy models for the DMH MR Tool database"""

from datetime import datetime
from enum import IntEnum
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


class DownloadStatus(IntEnum):
    """Download status enumeration"""
    NOT_DOWNLOADED = 0
    DOWNLOADED = 1
    FAILED = 2
    IN_PROGRESS = 3


class AsxInfo(Base):
    """ASX announcement information model"""
    __tablename__ = 'asx_info'

    id = Column(Integer, primary_key=True, autoincrement=True)
    asx_code = Column(String(10), nullable=False)
    title = Column(Text, nullable=False)
    pub_date = Column(Date, nullable=False)
    pdf_mask_url = Column(Text)
    pdf_url = Column(Text)
    page_num = Column(Integer, nullable=False)
    file_size = Column(Text, nullable=False)
    downloaded = Column(Integer, default=DownloadStatus.NOT_DOWNLOADED)
    update_timestamp = Column(DateTime, default=func.now(), onupdate=func.now())
    update_user = Column(String(100), nullable=False)

    # Relationships
    asx_nz_data = relationship("AsxNzData", back_populates="info")

    __table_args__ = (
        Index('idx_asx_info_code_date', 'asx_code', 'pub_date'),
    )

    def __repr__(self):
        return f"<AsxInfo(id={self.id}, asx_code='{self.asx_code}', title='{self.title[:30]}...')>"


class AsxNzData(Base):
    """ASX/NZ parsed financial data model"""
    __tablename__ = 'asx_nz_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    asx_code = Column(String(10))
    info_id = Column(Integer, ForeignKey('asx_info.id'), nullable=False)
    pub_date = Column(Date)
    asset_id = Column(String(20))
    ex_date = Column(Date)
    pay_date = Column(Date)
    currency = Column(String(3))
    income_rate = Column(Float(precision=8))
    aud2nzd = Column(Float(precision=8))
    franked_pct = Column(Float(precision=8))
    total = Column(Float(precision=8))
    unfranked_pct = Column(Float(precision=8))
    supplementary_dividend = Column(Float(precision=8))
    tax_rate = Column(Float(precision=8))

    # Relationships
    info = relationship("AsxInfo", back_populates="asx_nz_data")

    __table_args__ = (
        Index('idx_asx_nz_code_exdate', 'asx_code', 'ex_date'),
        Index('idx_asx_nz_info_id', 'info_id'),
    )

    def __repr__(self):
        return f"<AsxNzData(id={self.id}, asx_code='{self.asx_code}', asset_id='{self.asset_id}')>"


class VanguardData(Base):
    """Vanguard fund data model"""
    __tablename__ = 'vanguard_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    port_id = Column(String(20))
    fund_name = Column(String(200))
    ticker = Column(String(10))
    apir = Column(String(20))
    fund_currency = Column(String(3))
    as_of_date = Column(Date)
    ex_dividend_date = Column(Date)
    payable_date = Column(Date)
    reinvestment_date = Column(Date)
    record_date = Column(Date)
    cpu = Column(String(50))
    update_timestamp = Column(DateTime, default=func.now())

    # Component columns (dynamically added based on requirements, usually it is more than 100)
    CGCL = Column(Float)
    CGDW = Column(Float)
    ZIDU = Column(Float)
    FIIN = Column(Float)
    INC = Column(Float)
    # Add other component columns as needed

    __table_args__ = (
        Index('idx_vanguard_port_id', 'port_id'),
        UniqueConstraint('ticker', 'apir', 'reinvestment_date',
                         name='uq_vanguard_ticker_apir_date'),
    )

    def __repr__(self):
        return f"<VanguardData(id={self.id}, ticker='{self.ticker}', fund_name='{self.fund_name[:30]}...')>"


class VanguardMapping(Base):
    """Vanguard to DMH asset mapping"""
    __tablename__ = 'vanguard_mapping'

    id = Column(Integer, primary_key=True, autoincrement=True)
    port_id = Column(String(20))
    asset_id = Column(String(20))
    ticker = Column(String(10))
    apir = Column(String(20))
    is_valid = Column(Boolean, default=True)
    update_timestamp = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_vanguard_map_port_id', 'port_id'),
        Index('idx_vanguard_map_asset_ticker_apir', 'asset_id', 'ticker', 'apir'),
    )

    def __repr__(self):
        return f"<VanguardMapping(port_id='{self.port_id}', asset_id='{self.asset_id}')>"


class ColumnMap(Base):
    """Component code mapping between Vanguard and DMH"""
    __tablename__ = 'column_map'

    id = Column(Integer, primary_key=True, autoincrement=True)
    v_code = Column(String(50), comment="Component code in Vanguard")
    v_desc = Column(Text, comment="Description in Vanguard")
    d_code = Column(String(50), comment="Component code in DMH")
    d_desc = Column(Text, comment="Description in DMH")
    is_valid = Column(Boolean, default=True)
    update_timestamp = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<ColumnMap(v_code='{self.v_code}', d_code='{self.d_code}')>"


class SystemLog(Base):
    """System activity log"""
    __tablename__ = 'sys_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    update_timestamp = Column(DateTime, default=func.now())
    user_id = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    detail = Column(Text)
    success = Column(Boolean, default=True)
    duration_ms = Column(Integer)

    __table_args__ = (
        Index('idx_sys_log_timestamp', 'update_timestamp'),
        Index('idx_sys_log_user_action', 'user_id', 'action'),
    )

    def __repr__(self):
        return f"<SystemLog(id={self.id}, user='{self.user_id}', action='{self.action}')>"
