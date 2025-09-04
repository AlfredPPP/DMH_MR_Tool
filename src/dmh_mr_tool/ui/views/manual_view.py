from ui.views.base_view import BaseInterface


class ManualInterface(BaseInterface):
    def __init__(self, parent=None):
        super().__init__(title="ManualInterface", subtitle="ManualInterface", parent=parent)
        self.setObjectName('manualInterface')