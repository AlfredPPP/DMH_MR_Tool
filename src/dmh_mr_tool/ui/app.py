# src/dmh_mr_tool/ui/app.py
"""Main application entry point and QApplication setup"""

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon, QPalette, QColor
import structlog

from ..config.settings import get_config, ConfigManager
from ..database.connection import DatabaseManager
from .main_window import MainWindow

logger = structlog.get_logger()


class DMHApplication(QApplication):
    """Main application class with resource management"""

    def __init__(self, argv):
        super().__init__(argv)

        # Set application metadata
        self.setApplicationName("DMH MR Tool")
        self.setOrganizationName("Your Company")
        self.setApplicationDisplayName("DMH Master Rate Tool")

        # Initialize components
        self.config_manager = ConfigManager()
        self.db_manager: Optional[DatabaseManager] = None
        self.main_window: Optional[MainWindow] = None

        # Set up thread pool for async operations
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)

        # Apply application style
        self._setup_style()

    def _setup_style(self):
        """Configure application appearance"""
        self.setStyle("Fusion")

        # Dark theme palette
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.black)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)

    def initialize(self, config_path: Optional[Path] = None) -> bool:
        """
        Initialize application components

        Returns:
            True if initialization successful
        """
        try:
            # Load configuration
            config = self.config_manager.load(config_path)
            logger.info("Configuration loaded", env=config.environment)

            # Initialize database
            self.db_manager = DatabaseManager(config.database)
            self.db_manager.initialize()
            logger.info("Database initialized")

            # Create main window
            self.main_window = MainWindow(self)
            self.main_window.show()

            return True

        except Exception as e:
            logger.error("Failed to initialize application", error=str(e))
            QMessageBox.critical(
                None,
                "Initialization Error",
                f"Failed to initialize application:\n{str(e)}"
            )
            return False

    def cleanup(self):
        """Clean up resources before exit"""
        try:
            # Wait for thread pool to finish
            self.thread_pool.waitForDone(5000)

            # Close database
            if self.db_manager:
                self.db_manager.close()

            logger.info("Application cleanup completed")

        except Exception as e:
            logger.error("Error during cleanup", error=str(e))


def main():
    """Main entry point"""
    app = DMHApplication(sys.argv)

    # Initialize application
    if not app.initialize():
        sys.exit(1)

    # Run event loop
    exit_code = app.exec()

    # Cleanup
    app.cleanup()

    sys.exit(exit_code)