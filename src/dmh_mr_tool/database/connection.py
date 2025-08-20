# src/dmh_mr_tool/database/connection.py
"""Database connection manager with connection pooling and context management"""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional

import aiosqlite
from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
import structlog

from ..config.settings import DatabaseConfig
from ..core.logging import log_execution
from .models import Base

logger = structlog.get_logger()


class DatabaseManager:
    """Database connection manager with sync and async support"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self._async_connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    @log_execution(log_args=False)
    def initialize(self) -> None:
        """Initialize database engine and create tables"""
        # Ensure database directory exists
        self.config.path.parent.mkdir(parents=True, exist_ok=True)

        # Create engine with connection pooling
        self.engine = create_engine(
            f"sqlite:///{self.config.path}",
            echo=self.config.echo,
            poolclass=pool.NullPool,
            connect_args={
                "check_same_thread": False,
                "timeout": 30
            }
        )

        # Enable foreign keys for SQLite
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            cursor.close()

        # Create session factory
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False
        )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        logger.info("Database initialized", path=str(self.config.path))

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope for database operations

        Example:
            with db_manager.session() as session:
                user = session.query(User).filter_by(id=1).first()
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @asynccontextmanager
    async def async_session(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        Provide async database connection

        Example:
            async with db_manager.async_session() as conn:
                async with conn.execute("SELECT * FROM users") as cursor:
                    rows = await cursor.fetchall()
        """
        async with self._lock:
            if not self._async_connection:
                self._async_connection = await aiosqlite.connect(
                    str(self.config.path),
                    timeout=30
                )
                await self._async_connection.execute("PRAGMA foreign_keys=ON")
                await self._async_connection.execute("PRAGMA journal_mode=WAL")

            try:
                yield self._async_connection
                await self._async_connection.commit()
            except Exception:
                await self._async_connection.rollback()
                raise

    @log_execution()
    def backup(self, backup_path: Optional[Path] = None) -> Path:
        """
        Create a backup of the database

        Args:
            backup_path: Optional custom backup path

        Returns:
            Path to the backup file
        """
        import shutil
        from datetime import datetime

        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.config.backup_path / f"dmh_backup_{timestamp}.db"

        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.config.path, backup_path)

        logger.info("Database backed up", backup_path=str(backup_path))
        return backup_path

    def close(self) -> None:
        """Close database connections"""
        if self.engine:
            self.engine.dispose()

        if self._async_connection:
            asyncio.create_task(self._async_connection.close())

        logger.info("Database connections closed")

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()