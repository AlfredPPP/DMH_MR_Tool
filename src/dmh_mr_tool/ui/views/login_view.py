from ui.views.base_view import BaseInterface


class LoginInterface(BaseInterface):
    def __init__(self, parent=None):
        super().__init__(title="LoginInterface", subtitle="LoginInterface", parent=parent)
        self.setObjectName('loginInterface')

    def showLoginWindow(self, a):
        pass
