import functools
import inspect
import traceback

from PySide6.QtCore import Qt

from qfluentwidgets import InfoBar, InfoBarPosition


def raise_error_bar_in_class(func):
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                print("Error!")
                createErrorInfoBar(self, traceback.format_exc(), title=str(e))
                raise

        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                print("Error!")
                createErrorInfoBar(self, traceback.format_exc(), title=str(e))
                raise

        return sync_wrapper


def createErrorInfoBar(self, content, title="Unknown Error"):
    InfoBar.error(
        title=title,
        content=content,
        orient=Qt.Vertical,
        isClosable=True,
        position=InfoBarPosition.TOP_RIGHT,
        duration=-1,
        parent=self
    )


def createWarningInfoBar(self, title, content):
    InfoBar.warning(
        title=title,
        content=content,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP_RIGHT,
        duration=-1,
        parent=self
    )


def createSuccessInfoBar(self, title, content):
    InfoBar.success(
        title=title,
        content=content,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP_RIGHT,
        duration=-1,
        parent=self
    )
