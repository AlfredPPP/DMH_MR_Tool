# src/dmh_mr_tool/ui/utils/signal_bus.py
"""Signal bus for cross-component communication"""

from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """
    Global signal bus for application-wide communication
    """

    # InfoBar signals
    """
    infoBarSignal
    Signal sent to MainWindow to pop up an info bar, 3 str params stand for: info_type, title, message
        :info_type : "SUCCESS", "WARNING" or "ERROR"
        :title : text in infoBar title
        :message : text in infoBar context
    """
    infoBarSignal = Signal(str, str, str)

    # Spider progress signals
    """
    spiderProgressSignal
    Signal for tracking spider progress
        :source : str - Source name (e.g., "ASX", "Vanguard")
        :current : int - Current progress count
        :total : int - Total items to process
    """
    spiderProgressSignal = Signal(str, int, int)

    # Parser signals
    """
    parserCompleteSignal
    Signal emitted when parsing is complete
        :success : bool - Whether parsing was successful
        :data : dict - Parsed data payload
    """
    parserCompleteSignal = Signal(bool, dict)

    # MR Update signals
    """
    mrUpdateSignal
    Signal for MR update operations
        :action : str - Action type ("add", "update", "delete")
        :data : dict - Data payload
    """
    mrUpdateSignal = Signal(str, dict)

    # Database signals
    """
    databaseChangedSignal
    Signal emitted when database is modified
        :table : str - Table name that was modified
        :operation : str - Operation type ("insert", "update", "delete")
    """
    databaseChangedSignal = Signal(str, str)


# Global instance
signalBus = SignalBus()