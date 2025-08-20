# src/dmh_mr_tool/core/logging.py
"""Logging configuration with structured logging and decorators"""

import functools
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
import uuid

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder


def setup_logging(
        level: str = "INFO",
        log_file: Optional[Path] = None,
        max_bytes: int = 5_242_880,
        backup_count: int = 5,
        enable_console: bool = True,
        enable_file: bool = True
) -> None:
    """
    Configure structured logging for the application

    Args:
        level: Logging level
        log_file: Path to log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        enable_console: Whether to print log on the console
        enable_file: Whether to start log file handler with rotation
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            CallsiteParameterAdder(
                parameters=[
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                ]
            ),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file and enable_file:
        from logging.handlers import RotatingFileHandler

        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        root_logger.addHandler(file_handler)


def log_execution(
        log_args: bool = True,
        log_result: bool = False,
        log_exceptions: bool = True,
        timed: bool = True
) -> Callable:
    """
    Decorator to log function execution with optional timing

    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        log_exceptions: Whether to log exceptions
        timed: Whether to time the execution

    Example:
        @log_execution(log_args=True, timed=True)
        def process_data(data: dict) -> dict:
            return transform(data)
    """

    def decorator(func: Callable) -> Callable:
        logger = structlog.get_logger(func.__module__)

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate correlation ID for this execution
            correlation_id = str(uuid.uuid4())[:8]

            # Build context
            context = {
                "function": func.__name__,
                "correlation_id": correlation_id
            }

            if log_args:
                context["args"] = str(args)[:200]  # Truncate long args
                context["kwargs"] = str(kwargs)[:200]

            # Log start
            logger.info(f"Executing {func.__name__}", **context)

            start_time = datetime.now() if timed else None

            try:
                result = func(*args, **kwargs)

                # Log success
                success_context = {**context}
                if timed:
                    duration = (datetime.now() - start_time).total_seconds()
                    success_context["duration_seconds"] = duration

                if log_result:
                    success_context["result"] = str(result)[:200]

                logger.info(f"Completed {func.__name__}", **success_context)

                return result

            except Exception as e:
                # Log exception
                if log_exceptions:
                    error_context = {
                        **context,
                        "exception": str(e),
                        "traceback": traceback.format_exc()
                    }

                    if timed and start_time:
                        duration = (datetime.now() - start_time).total_seconds()
                        error_context["duration_seconds"] = duration

                    logger.error(f"Failed {func.__name__}", **error_context)

                raise

        return wrapper

    return decorator


def log_async_execution(
        log_args: bool = True,
        log_result: bool = False,
        log_exceptions: bool = True,
        timed: bool = True
) -> Callable:
    """
    Decorator for async functions with logging

    Similar to log_execution but for async functions
    """

    def decorator(func: Callable) -> Callable:
        logger = structlog.get_logger(func.__module__)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            correlation_id = str(uuid.uuid4())[:8]

            context = {
                "function": func.__name__,
                "correlation_id": correlation_id,
                "async": True
            }

            if log_args:
                context["args"] = str(args)[:200]
                context["kwargs"] = str(kwargs)[:200]

            logger.info(f"Executing async {func.__name__}", **context)

            start_time = datetime.now() if timed else None

            try:
                result = await func(*args, **kwargs)

                success_context = {**context}
                if timed:
                    duration = (datetime.now() - start_time).total_seconds()
                    success_context["duration_seconds"] = duration

                if log_result:
                    success_context["result"] = str(result)[:200]

                logger.info(f"Completed async {func.__name__}", **success_context)

                return result

            except Exception as e:
                if log_exceptions:
                    error_context = {
                        **context,
                        "exception": str(e),
                        "traceback": traceback.format_exc()
                    }

                    if timed and start_time:
                        duration = (datetime.now() - start_time).total_seconds()
                        error_context["duration_seconds"] = duration

                    logger.error(f"Failed async {func.__name__}", **error_context)

                raise

        return wrapper

    return decorator


class ContextLogger:
    """
    Context manager for logging with additional context

    Example:
        with ContextLogger("data_processing", user="john", task_id="123"):
            process_data()
            validate_results()
    """

    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.logger = structlog.get_logger()
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting {self.operation}", **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation}",
                duration_seconds=duration,
                **self.context
            )
        else:
            self.logger.error(
                f"Failed {self.operation}",
                duration_seconds=duration,
                exception=str(exc_val),
                traceback=traceback.format_exc(),
                **self.context
            )

        return False  # Don't suppress exceptions