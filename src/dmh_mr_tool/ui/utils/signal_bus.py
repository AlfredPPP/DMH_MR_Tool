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

    """
    spiderProgressSignal
    Signal sent from spider operations to update progress, 2 params: progress_value, message
        :progress_value : int (0-100) representing progress percentage
        :message : str describing current operation
    """
    spiderProgressSignal = Signal(int, str)

    """
    spiderLogSignal
    Signal sent from spider operations to log messages
        :message : str log message to display
    """
    spiderLogSignal = Signal(str)


signalBus = SignalBus()