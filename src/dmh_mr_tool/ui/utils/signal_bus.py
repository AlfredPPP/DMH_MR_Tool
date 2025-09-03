from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """
    infoBarSignal
    Signal sent to MainWindow to pop up an info bar, 3 str params stand for: info_type, title, message
        :info_type : "SUCCESS", "WARNING" or "ERROR"
        :title : text in infoBar title
        :message : text in infoBar context
    """
    infoBarSignal = Signal(str, str, str)


signalBus = SignalBus()
