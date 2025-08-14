# src/dmh_mr_tool/database/repositories/base.py
"""Base repository pattern for data access"""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from ..models import Base

logger = structlog.get_logger()

T = TypeVar('T', bound=Base)


class BaseRepository(ABC, Generic[T]):
    """Base repository with common CRUD operations"""

    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model

    def get(self, id: int) -> Optional[T]:
        """Get entity by ID"""
        try:
            return self.session.query(self.model).filter(
                self.model.id == id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__}",
                         id=id, error=str(e))
            raise

    def get_all(self, limit: int = None, offset: int = None) -> List[T]:
        """Get all entities with optional pagination"""
        try:
            query = self.session.query(self.model)
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model.__name__}",
                         error=str(e))
            raise

    def create(self, **kwargs) -> T:
        """Create new entity"""
        try:
            entity = self.model(**kwargs)
            self.session.add(entity)
            self.session.flush()
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model.__name__}",
                         data=kwargs, error=str(e))
            raise

    def update(self, id: int, **kwargs) -> Optional[T]:
        """Update entity by ID"""
        try:
            entity = self.get(id)
            if entity:
                for key, value in kwargs.items():
                    setattr(entity, key, value)
                self.session.flush()
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model.__name__}",
                         id=id, data=kwargs, error=str(e))
            raise

    def delete(self, id: int) -> bool:
        """Delete entity by ID"""
        try:
            entity = self.get(id)
            if entity:
                self.session.delete(entity)
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model.__name__}",
                         id=id, error=str(e))
            raise

    def exists(self, **kwargs) -> bool:
        """Check if entity exists with given criteria"""
        try:
            query = self.session.query(self.model)
            for key, value in kwargs.items():
                query = query.filter(getattr(self.model, key) == value)
            return query.first() is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model.__name__}",
                         criteria=kwargs, error=str(e))
            raise