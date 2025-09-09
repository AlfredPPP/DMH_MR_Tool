# src/dmh_mr_tool/database/repositories/base.py
"""Base repository class with common database operations"""

from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

import structlog

logger = structlog.get_logger()

# Type variable for SQLAlchemy models
T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Base repository class providing common CRUD operations

    Type Parameters:
        T: SQLAlchemy model class
    """

    def __init__(self, session: Session, model: Type[T]):
        """
        Initialize repository

        Args:
            session: SQLAlchemy session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get a single record by ID

        Args:
            id: Primary key value

        Returns:
            Model instance or None if not found
        """
        try:
            return self.session.query(self.model).filter(
                self.model.id == id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by id",
                         id=id, error=str(e))
            return None

    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """
        Get all records with optional pagination

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of model instances
        """
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
            return []

    def create(self, **kwargs) -> Optional[T]:
        """
        Create a new record

        Args:
            **kwargs: Field values for the new record

        Returns:
            Created model instance or None if failed
        """
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            self.session.commit()
            self.session.refresh(instance)

            logger.debug(f"Created {self.model.__name__}", id=instance.id)
            return instance

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error creating {self.model.__name__}",
                         error=str(e), kwargs=kwargs)
            return None

    def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Update an existing record

        Args:
            id: Primary key value
            **kwargs: Field values to update

        Returns:
            Updated model instance or None if failed
        """
        try:
            instance = self.get_by_id(id)
            if not instance:
                logger.warning(f"{self.model.__name__} not found for update",
                               id=id)
                return None

            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            self.session.commit()
            self.session.refresh(instance)

            logger.debug(f"Updated {self.model.__name__}", id=id)
            return instance

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error updating {self.model.__name__}",
                         id=id, error=str(e))
            return None

    def delete(self, id: int) -> bool:
        """
        Delete a record

        Args:
            id: Primary key value

        Returns:
            True if successful, False otherwise
        """
        try:
            instance = self.get_by_id(id)
            if not instance:
                logger.warning(f"{self.model.__name__} not found for deletion",
                               id=id)
                return False

            self.session.delete(instance)
            self.session.commit()

            logger.debug(f"Deleted {self.model.__name__}", id=id)
            return True

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error deleting {self.model.__name__}",
                         id=id, error=str(e))
            return False

    def bulk_create(self, records: List[Dict[str, Any]]) -> int:
        """
        Create multiple records in a single transaction

        Args:
            records: List of dictionaries with field values

        Returns:
            Number of records created
        """
        try:
            instances = [self.model(**record) for record in records]
            self.session.bulk_save_objects(instances)
            self.session.commit()

            logger.debug(f"Bulk created {len(instances)} {self.model.__name__} records")
            return len(instances)

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error bulk creating {self.model.__name__}",
                         error=str(e), count=len(records))
            return 0

    def exists(self, **kwargs) -> bool:
        """
        Check if a record exists with given criteria

        Args:
            **kwargs: Field values to filter by

        Returns:
            True if exists, False otherwise
        """
        try:
            query = self.session.query(self.model)

            for key, value in kwargs.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

            return query.first() is not None

        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model.__name__}",
                         error=str(e), kwargs=kwargs)
            return False

    def filter(self, **kwargs) -> List[T]:
        """
        Get records matching given criteria

        Args:
            **kwargs: Field values to filter by

        Returns:
            List of matching model instances
        """
        try:
            query = self.session.query(self.model)

            for key, value in kwargs.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

            return query.all()

        except SQLAlchemyError as e:
            logger.error(f"Error filtering {self.model.__name__}",
                         error=str(e), kwargs=kwargs)
            return []