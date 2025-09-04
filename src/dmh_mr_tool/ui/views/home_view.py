from ui.views.base_view import BaseInterface


class HomeInterface(BaseInterface):
    def __init__(self, parent=None):
        super().__init__(title="HomeInterface", subtitle="HomeInterface", parent=parent)
        self.setObjectName('homeInterface')
