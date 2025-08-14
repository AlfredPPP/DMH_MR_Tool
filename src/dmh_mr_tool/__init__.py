# src/dmh_mr_tool/__init__.py
"""DMH MR Tool - Financial Market Data Processing Automation"""

__version__ = "1.0.0"
__author__ = "Your Team"

from .core.logging import setup_logging

# Initialize logging on import
setup_logging()