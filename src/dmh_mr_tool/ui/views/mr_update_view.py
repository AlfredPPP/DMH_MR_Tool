from ui.views.base_view import BaseInterface


class MrUpdateInterface(BaseInterface):
    def __init__(self, parent=None):
        super().__init__(title="MrUpdateInterface", subtitle="MrUpdateInterface", parent=parent)
        self.setObjectName('mrUpdateInterface')