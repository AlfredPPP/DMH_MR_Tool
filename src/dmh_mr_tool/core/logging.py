"""Logging configuration with structured logging and decorators"""

import functools
import logging
import sys
import traceback
import inspect
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
import uuid

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder


def sanitize_for_json(value: Any) -> str:
    """
    Convert value to string and replace double quotes with single quotes
    to prevent JSON parsing issues
    """
    if value is None:
        return ""
    # Convert to string and replace double quotes with single quotes
    return str(value).replace('"', "'")


class CustomJSONRenderer:
    """Custom JSON renderer that ensures proper field ordering and quote handling"""

    def __init__(self, field_order=None):
        self.field_order = field_order or [
            "function", "correlation_id", "logger", "event",
            "source_lineno", "caller_lineno", "args", "kwargs",
            "duration_seconds", "level", "timestamp"
        ]

    def __call__(self, logger, name, event_dict):
        import json

        # Create ordered dict with specified field order
        ordered = {}

        # First, add fields in the specified order if they exist
        for field in self.field_order:
            if field in event_dict:
                # Sanitize the value to replace double quotes
                ordered[field] = sanitize_for_json(event_dict[field])

        # Add any remaining fields not in the specified order
        for key, value in event_dict.items():
            if key not in ordered:
                # Special handling for certain fields
                if key in ["exception", "traceback", "result", "call_stack"]:
                    ordered[key] = sanitize_for_json(value)
                elif key == "event":
                    # event field is already handled, skip if it appears again
                    continue
                else:
                    ordered[key] = sanitize_for_json(value)

        return json.dumps(ordered, ensure_ascii=False)


def get_function_source_info(func):
    """
    Get source info for a specific function

    Args:
        func: The function object to get source info from
    """
    try:
        source_file = inspect.getsourcefile(func)
        source_lines, source_lineno = inspect.getsourcelines(func)
        # Get the module path relative to project root if possible
        module_path = func.__module__
        return {
            'source_file': Path(source_file).name if source_file else None,
            'source_module': module_path,
            'source_lineno': source_lineno,
            'source_function': func.__name__
        }
    except (TypeError, OSError):
        return {
            'source_file': None,
            'source_module': func.__module__ if func else None,
            'source_lineno': None,
            'source_function': func.__name__ if func else None
        }


def get_caller_info(skip_frames=2):
    """
    Get info about the caller of the decorated function

    Args:
        skip_frames: Number of frames to skip (usually 2 for decorator context)
    """
    frame = inspect.currentframe()
    try:
        # Skip the specified number of frames
        for _ in range(skip_frames):
            if frame:
                frame = frame.f_back

        # Now find the first frame outside logging.py
        while frame:
            filename = frame.f_code.co_filename
            if not filename.endswith('logging.py'):
                # Try to get the module name from the frame
                module_name = frame.f_globals.get('__name__', '')
                return {
                    'caller_file': Path(filename).name,
                    'caller_module': module_name,
                    'caller_lineno': frame.f_lineno,
                    'caller_function': frame.f_code.co_name
                }
            frame = frame.f_back

        return {'caller_file': None, 'caller_module': None, 'caller_lineno': None, 'caller_function': None}
    finally:
        del frame


def get_call_stack(max_depth=5):
    """
    Get a simplified call stack for tracking execution flow

    Args:
        max_depth: Maximum depth of call stack to capture
    """
    stack = []
    frame = inspect.currentframe()
    try:
        # Skip current frame
        frame = frame.f_back
        depth = 0

        while frame and depth < max_depth:
            filename = frame.f_code.co_filename
            # Skip logging module frames
            if not filename.endswith('logging.py'):
                stack.append({
                    'file': Path(filename).name,
                    'function': frame.f_code.co_name,
                    'line': frame.f_lineno
                })
                depth += 1
            frame = frame.f_back

        return stack
    finally:
        del frame


def setup_logging(
        level: str = "INFO",
        log_file: Optional[Path] = None,
        max_bytes: int = 5_242_880,
        backup_count: int = 5,
        enable_console: bool = True,
        enable_file: bool = True,
        include_call_stack: bool = False  # New parameter
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
        include_call_stack: Whether to include call stack in logs
    """
    # Store configuration in logging module for access by decorators
    logging.include_call_stack = include_call_stack

    # Configure structlog with custom renderer
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            CustomJSONRenderer(field_order=[
                "function", "correlation_id", "logger", "event",
                "source_lineno", "caller_lineno", "args", "kwargs",
                "duration_seconds", "level", "timestamp"
            ])
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

        log_file.parent.mkdir(exist_ok=True)
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
        timed: bool = True,
        include_caller: bool = True  # New parameter
) -> Callable:
    """
    Decorator to log function execution with optional timing

    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        log_exceptions: Whether to log exceptions
        timed: Whether to time the execution
        include_caller: Whether to include caller information

    Example:
        @log_execution(log_args=True, timed=True)
        def process_data(data: dict) -> dict:
            return transform(data)
    """

    def decorator(func: Callable) -> Callable:
        # Use the function's module for the logger
        logger = structlog.get_logger(func.__module__)

        # Get source info once when decorator is applied
        source_info = get_function_source_info(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate correlation ID for this execution
            correlation_id = str(uuid.uuid4())[:8]

            # Build context with source info
            context = {
                "function": func.__name__,
                "correlation_id": correlation_id,
                "source_lineno": source_info.get('source_lineno')
            }

            # Add caller info if requested
            if include_caller:
                caller_info = get_caller_info(skip_frames=1)
                context["caller_lineno"] = caller_info.get('caller_lineno')
                context["caller_module"] = caller_info.get('caller_module')
                context["caller_function"] = caller_info.get('caller_function')

            # Add call stack if globally enabled
            if hasattr(logging, 'include_call_stack') and logging.include_call_stack:
                context["call_stack"] = sanitize_for_json(get_call_stack())

            if log_args:
                # Sanitize args and kwargs for JSON
                context["args"] = sanitize_for_json(args)[:200]  # Truncate long args
                context["kwargs"] = sanitize_for_json(kwargs)[:200]

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
                    success_context["result"] = sanitize_for_json(result)[:200]

                logger.info(f"Completed {func.__name__}", **success_context)

                return result

            except Exception as e:
                # Get the actual error location from traceback
                tb = traceback.extract_tb(e.__traceback__)
                if tb:
                    # Find the actual error frame (last frame in the decorated function)
                    for frame in reversed(tb):
                        if frame.filename.endswith(Path(source_info.get('source_file', '')).name):
                            context["source_lineno"] = frame.lineno
                            context["error_line"] = frame.lineno  # Add explicit error line
                            context["error_text"] = sanitize_for_json(frame.line)  # Add the actual line of code
                            break

                # Log exception
                if log_exceptions:
                    error_context = {
                        **context,
                        "exception": sanitize_for_json(e),
                        "exception_type": type(e).__name__,
                        "traceback": sanitize_for_json(traceback.format_exc())
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
        timed: bool = True,
        include_caller: bool = True
) -> Callable:
    """
    Decorator for async functions with logging

    Similar to log_execution but for async functions
    """

    def decorator(func: Callable) -> Callable:
        logger = structlog.get_logger(func.__module__)

        # Get source info once when decorator is applied
        source_info = get_function_source_info(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            correlation_id = str(uuid.uuid4())[:8]

            # Build context with source info
            context = {
                "function": func.__name__,
                "correlation_id": correlation_id,
                "source_lineno": source_info.get('source_lineno'),
                "async": True
            }

            # Add caller info if requested
            if include_caller:
                caller_info = get_caller_info(skip_frames=1)
                context["caller_lineno"] = caller_info.get('caller_lineno')
                context["caller_module"] = caller_info.get('caller_module')
                context["caller_function"] = caller_info.get('caller_function')

            # Add call stack if globally enabled
            if hasattr(logging, 'include_call_stack') and logging.include_call_stack:
                context["call_stack"] = sanitize_for_json(get_call_stack())

            if log_args:
                context["args"] = sanitize_for_json(args)[:200]
                context["kwargs"] = sanitize_for_json(kwargs)[:200]

            logger.info(f"Executing async {func.__name__}", **context)

            start_time = datetime.now() if timed else None

            try:
                result = await func(*args, **kwargs)

                success_context = {**context}
                if timed:
                    duration = (datetime.now() - start_time).total_seconds()
                    success_context["duration_seconds"] = duration

                if log_result:
                    success_context["result"] = sanitize_for_json(result)[:200]

                logger.info(f"Completed async {func.__name__}", **success_context)

                return result

            except Exception as e:
                # Get the actual error location from traceback
                tb = traceback.extract_tb(e.__traceback__)
                if tb:
                    for frame in reversed(tb):
                        if frame.filename.endswith(Path(source_info.get('source_file', '')).name):
                            context["source_lineno"] = frame.lineno
                            context["error_line"] = frame.lineno
                            context["error_text"] = sanitize_for_json(frame.line)
                            break

                if log_exceptions:
                    error_context = {
                        **context,
                        "exception": sanitize_for_json(e),
                        "exception_type": type(e).__name__,
                        "traceback": sanitize_for_json(traceback.format_exc())
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

    def __init__(self, operation: str, include_caller: bool = True, **context):
        self.operation = operation
        self.context = context
        self.logger = structlog.get_logger()
        self.start_time = None
        self.include_caller = include_caller

        # Get caller info when context is created
        if self.include_caller:
            caller_info = get_caller_info(skip_frames=2)
            self.context["caller_lineno"] = caller_info.get('caller_lineno')
            self.context["caller_module"] = caller_info.get('caller_module')

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
            # Get the actual error location from traceback
            if exc_tb:
                tb = traceback.extract_tb(exc_tb)
                if tb:
                    # Find the first frame not in logging.py
                    for frame in tb:
                        if not frame.filename.endswith('logging.py'):
                            self.context["error_line"] = frame.lineno
                            self.context["error_file"] = Path(frame.filename).name
                            self.context["error_text"] = sanitize_for_json(frame.line)
                            break

            self.logger.error(
                f"Failed {self.operation}",
                duration_seconds=duration,
                exception=sanitize_for_json(exc_val),
                exception_type=type(exc_val).__name__ if exc_val else None,
                traceback=sanitize_for_json(traceback.format_exc()),
                **self.context
            )

        return False  # Don't suppress exceptions