# src/dmh_mr_tool/ui/main_window.py
"""Main window controller with navigation"""

import asyncio
import os
import sys
import structlog
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from qfluentwidgets import FluentWindow, SystemThemeListener, isDarkTheme, NavigationItemPosition, \
    NavigationAvatarWidget
from qfluentwidgets import FluentIcon as FIF

from qasync import QEventLoop

from core.utils import USERNAME
from ui.views.home_view import HomeInterface
from ui.views.db_browser_view import DBBrowserInterface
from ui.views.settings_view import SettingsInterface
from ui.views.spider_view import SpiderInterface
from ui.views.manual_view import ManualInterface
from ui.views.mr_update_view import MrUpdateInterface
from ui.views.parser_view import ParserInterface
from ui.views.login_view import LoginInterface
from ui.resource import resource
from ui.utils.config import cfg
from ui.utils.infobar import createErrorInfoBar, createSuccessInfoBar, createWarningInfoBar
from ui.utils.signal_bus import signalBus
from business.services.dmh_service import DMH

logger = structlog.get_logger()


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.initWindow()

        # init services
        self.dmh = DMH()

        # create system theme listener
        self.themeListener = SystemThemeListener(self)

        # create sub interfaces
        self.homeInterface = HomeInterface(self)
        self.dbBrowserInterface = DBBrowserInterface(self)
        self.settingsInterface = SettingsInterface(self)
        self.spiderInterface = SpiderInterface(self)
        self.manualInterface = ManualInterface(self)
        self.mrUpdateInterface = MrUpdateInterface(self)
        self.parserInterface = ParserInterface(self)
        self.loginInterface = LoginInterface(self)

        # enable acrylic effect
        self.navigationInterface.setAcrylicEnabled(True)

        # add items to navigation
        self.initNavigation()

        # start theme listener
        self.themeListener.start()

        self.connectSignalToSlot()

    def connectSignalToSlot(self):
        signalBus.infoBarSignal.connect(self.show_session_infoBar)

    def initNavigation(self):
        # add navigation items
        self.addSubInterface(self.homeInterface, FIF.HOME, 'Home')
        self.navigationInterface.addSeparator()

        pos = NavigationItemPosition.SCROLL
        self.addSubInterface(self.spiderInterface, FIF.ROBOT, 'Spider', pos)
        self.addSubInterface(self.parserInterface, FIF.SYNC, 'Parser', pos)
        self.addSubInterface(self.mrUpdateInterface, FIF.UPDATE, 'MR Update', pos)
        self.addSubInterface(self.manualInterface, FIF.CLOUD, 'Manual', NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.dbBrowserInterface, FIF.DOCUMENT, 'DB Browser', NavigationItemPosition.BOTTOM)

        # add custom widget to bottom
        avatar = NavigationAvatarWidget(USERNAME)
        self.navigationInterface.addWidget(
            routeKey='avatar',
            widget=avatar,
            tooltip=os.getlogin(),
            onClick=lambda: self.loginInterface.showLoginWindow(avatar),
            position=NavigationItemPosition.BOTTOM
        )
        self.addSubInterface(self.settingsInterface, FIF.SETTING, 'Settings', NavigationItemPosition.BOTTOM)

    def initWindow(self):
        self.resize(760, 617)
        self.setWindowTitle("MR Maintenance Tool")
        self.setMinimumWidth(760)

        self.setMicaEffectEnabled(cfg.get(cfg.micaEnabled))

        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
        self.show()
        QApplication.processEvents()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'splashScreen'):
            self.splashScreen.resize(self.size())

    def closeEvent(self, e):
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        super().closeEvent(e)

    def _onThemeChangedFinished(self):
        super()._onThemeChangedFinished()
        # retry
        if self.isMicaEffectEnabled():
            QTimer.singleShot(100, lambda: self.windowEffect.setMicaEffect(self.winId(), isDarkTheme()))

    def show_session_infoBar(self, info_type: str, title: str, message: str):
        if info_type == "SUCCESS":
            createSuccessInfoBar(self, title, message)
        elif info_type == "WARNING":
            createWarningInfoBar(self, title, message)
        elif info_type == "ERROR":
            createErrorInfoBar(self, title, message)

def run():
    logger.info(f'Program start! User: {USERNAME}')
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = MainWindow()
    window.show()
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    run()
