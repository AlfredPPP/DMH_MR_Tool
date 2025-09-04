import asyncio
import aiohttp

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from config.settings import CONFIG
from ui.utils.signal_bus import signalBus

LOGIN_URL = CONFIG.dmh.login_url
POST_URL = CONFIG.dmh.post_url
BACKUP_PATH = CONFIG.paths.backup_path
CONCURRENCY = CONFIG.dmh.concurrent_limit


class DMH(QObject):
    def __init__(self):
        super().__init__()
        self.session = self.create_session()
        self.infoBarSignal = signalBus.infoBarSignal

    def _send_task_finish_signal(self, output: dict):
        if output['status'] == 'success':
            self.infoBarSignal.emit('SUCCESS', 'Success', f"{output['message']}")
        elif output['status'] == 'fail':
            self.infoBarSignal.emit('WARNING', f"{output['message']}", f"{output['result']}")

    def create_session(self):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._create_session())

    @staticmethod
    async def _create_session():
        return aiohttp.ClientSession()

    async def login(self, username: str, passcode: str) -> None:
        data = {"username":username, "PASSWORD": passcode}
        async with self.session.post(LOGIN_URL, data=data) as resp:
            content = await resp.text()
            if content.__contains__("displayName"):
                self.infoBarSignal.emit('SUCCESS', 'Success', "DMH session login success!")
                print("DMH session login success!")
            else:
                print("DMH session login failed!")