from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QHBoxLayout

from qfluentwidgets import ScrollArea, isDarkTheme, TitleLabel, CaptionLabel, StrongBodyLabel
from ui.resource.style_sheet import StyleSheet


class SeparatorWidget(QWidget):
    """Horizontal separator widget"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(15)  # 仅固定高度，宽度由布局控制

    def paintEvent(self, e):
        painter = QPainter(self)
        pen = QPen(1)
        pen.setCosmetic(True)
        c = QColor(255, 255, 255, 21) if isDarkTheme() else QColor(0, 0, 0, 15)
        pen.setColor(c)
        painter.setPen(pen)

        y = self.height() // 2
        painter.drawLine(0, y, self.width(), y)


class PageHead(QWidget):
    def __init__(self, title, subtitle, parent=None):
        super().__init__(parent=parent)
        self.title_label = TitleLabel(title, self)
        self.subtitle_label = CaptionLabel(subtitle, self)

        self.vBoxLayout = QVBoxLayout(self)
        self.hBoxLayout = QHBoxLayout(self)
        self.buttonLayout = QHBoxLayout()

        self.__initWidget()

    def __initWidget(self):
        self.setFixedHeight(50)
        self.subtitle_label.setContentsMargins(0, 11, 0, 0)
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.setSpacing(10)
        self.hBoxLayout.addWidget(self.subtitle_label, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.addStretch(1)
        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(36, 12, 36, 0)
        self.vBoxLayout.addLayout(self.hBoxLayout)
        self.vBoxLayout.setSpacing(4)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.subtitle_label.setTextColor(QColor(96, 96, 96), QColor(216, 216, 216))


class PageBody(QWidget):
    def __init__(self, title, widget: QWidget, stretch=0, parent=None):
        super().__init__(parent=parent)
        self.widget = widget
        self.stretch = stretch
        self.title_label = StrongBodyLabel(title, self)
        self.body = QFrame(self)
        self.vBoxLayout = QVBoxLayout(self)
        self.bodyLayout = QVBoxLayout(self.body)
        self.topLayout = QHBoxLayout(self)
        self.bottomLayout = QHBoxLayout(self)

        self.__initWidget()

    def __initWidget(self):
        self.__initLayout()
        self.body.setObjectName('body')

    def __initLayout(self):
        self.vBoxLayout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        self.bodyLayout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        self.topLayout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

        self.vBoxLayout.setSpacing(12)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.topLayout.setContentsMargins(12, 12, 12, 12)
        self.bottomLayout.setContentsMargins(18, 18, 18, 18)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)

        if self.title_label.text():
            self.vBoxLayout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.addWidget(self.body, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.bodyLayout.setSpacing(0)
        self.bodyLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bodyLayout.addLayout(self.topLayout, 0)

        self.widget.setParent(self.body)
        self.topLayout.addWidget(self.widget)
        if self.stretch == 0:
            self.topLayout.addStretch(1)

        self.widget.show()

        self.bottomLayout.addStretch(1)
        self.bottomLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


class BaseInterface(ScrollArea):
    """ Tool's base interface for every tab"""

    def __init__(self, title: str, subtitle: str, parent=None):
        """
        Parameters
        ----------
        title: str
            The title of tab

        subtitle: str
            The subtitle of tab

        parent: QWidget
            parent widget
        """
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.pageHead = PageHead(title, subtitle, self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, self.pageHead.height(), 0, 0)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setSpacing(30)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 20, 36, 36)

        self.view.setObjectName('view')
        StyleSheet.BASE_INTERFACE.apply(self)

    def addPageBody(self, title, widget, stretch=0):
        body = PageBody(title, widget, stretch, self.view)
        self.vBoxLayout.addWidget(body, 0, Qt.AlignmentFlag.AlignTop)
        return body

    def goToPage(self, index: int):
        """ Auto navigate to the specified page"""
        w = self.vBoxLayout.itemAt(index).widget()
        self.verticalScrollBar().setValue(w.y())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.pageHead.resize(self.width(), self.pageHead.height())
