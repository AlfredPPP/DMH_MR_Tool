# src/dmh_mr_tool/ui/main_window.py
"""Main window controller with navigation"""

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame,
    QMessageBox, QStatusBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence
import structlog

from .views.home_view import HomeView
from .views.spider_view import SpiderView
from .views.parser_view import ParserView
from .views.mr_update_view import MRUpdateView
from .views.db_browser_view import DBBrowserView
from .views.settings_view import SettingsView
from .widgets.navigation import NavigationPanel

logger = structlog.get_logger()


class MainWindow(QMainWindow):
    """Main application window with navigation and view management"""

    # Signals
    view_changed = Signal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.views: Dict[str, QWidget] = {}
        self.current_view: Optional[str] = None

        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._setup_status_bar()

        # Show home view by default
        self.switch_view("home")

    def _setup_ui(self):
        """Set up the main UI layout"""
        self.setWindowTitle("DMH Master Rate Tool")
        self.setMinimumSize(1200, 800)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Navigation panel
        self.nav_panel = NavigationPanel()
        self.nav_panel.view_selected.connect(self.switch_view)
        main_layout.addWidget(self.nav_panel)

        # Content area
        content_frame = QFrame()
        content_frame.setFrameStyle(QFrame.StyledPanel)
        content_layout = QVBoxLayout(content_frame)

        # View stack
        self.view_stack = QStackedWidget()
        content_layout.addWidget(self.view_stack)

        # Initialize views
        self._init_views()

        main_layout.addWidget(content_frame, 1)

    def _init_views(self):
        """Initialize all application views"""
        view_classes = {
            "home": HomeView,
            "spider": SpiderView,
            "parser": ParserView,
            "mr_update": MRUpdateView,
            "db_browser": DBBrowserView,
            "settings": SettingsView
        }

        for name, view_class in view_classes.items():
            view = view_class(self)
            self.views[name] = view
            self.view_stack.addWidget(view)

            # Connect view signals if needed
            if hasattr(view, 'status_message'):
                view.status_message.connect(self.show_status_message)

    def _setup_menu(self):
        """Set up application menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        backup_action = QAction("&Backup Database", self)
        backup_action.triggered.connect(self.backup_database)
        file_menu.addAction(backup_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        for name, view in self.views.items():
            action = QAction(f"&{name.replace('_', ' ').title()}", self)
            action.triggered.connect(lambda checked, n=name: self.switch_view(n))
            view_menu.addAction(action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        refresh_action = QAction("&Refresh Data", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self.refresh_current_view)
        tools_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts"""
        # Quick navigation shortcuts
        shortcuts = {
            "Ctrl+1": lambda: self.switch_view("home"),
            "Ctrl+2": lambda: self.switch_view("spider"),
            "Ctrl+3": lambda: self.switch_view("parser"),
            "Ctrl+4": lambda: self.switch_view("mr_update"),
            "Ctrl+5": lambda: self.switch_view("db_browser"),
            "Ctrl+6": lambda: self.switch_view("settings"),
        }

        for key, func in shortcuts.items():
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(func)
            self.addAction(action)

    def _setup_status_bar(self):
        """Set up status bar with permanent widgets"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # User label
        self.user_label = QLabel(f"User: {self.app.config_manager.config.user or 'Unknown'}")
        self.status_bar.addPermanentWidget(self.user_label)

        # Environment label
        env = self.app.config_manager.config.environment
        self.env_label = QLabel(f"Environment: {env}")
        self.status_bar.addPermanentWidget(self.env_label)

        # Connection status
        self.connection_label = QLabel("● Connected")
        self.connection_label.setStyleSheet("color: green;")
        self.status_bar.addPermanentWidget(self.connection_label)

    def switch_view(self, view_name: str):
        """Switch to a different view"""
        if view_name not in self.views:
            logger.error(f"Unknown view: {view_name}")
            return

        self.current_view = view_name
        view = self.views[view_name]
        self.view_stack.setCurrentWidget(view)

        # Update navigation
        self.nav_panel.set_active(view_name)

        # Emit signal
        self.view_changed.emit(view_name)

        logger.info(f"Switched to view: {view_name}")
        self.show_status_message(f"Switched to {view_name.replace('_', ' ').title()}")

    def refresh_current_view(self):
        """Refresh the current view"""
        if self.current_view and self.current_view in self.views:
            view = self.views[self.current_view]
            if hasattr(view, 'refresh'):
                view.refresh()
                self.show_status_message(f"Refreshed {self.current_view}")

    def show_status_message(self, message: str, timeout: int = 3000):
        """Show a temporary status message"""
        self.status_bar.showMessage(message, timeout)

    def backup_database(self):
        """Trigger database backup"""
        try:
            backup_path = self.app.db_manager.backup()
            QMessageBox.information(
                self,
                "Backup Complete",
                f"Database backed up to:\n{backup_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Backup Failed",
                f"Failed to backup database:\n{str(e)}"
            )

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About DMH MR Tool",
            "DMH Master Rate Tool v1.0.0\n\n"
            "Financial market data processing automation tool\n"
            "for Australian market data.\n\n"
            "© 2025 Your Company"
        )

    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
