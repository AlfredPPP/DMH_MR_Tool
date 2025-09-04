from ui.views.base_view import BaseInterface


class ParserInterface(BaseInterface):
    def __init__(self, parent=None):
        super().__init__(title="ParserInterface", subtitle="ParserInterface", parent=parent)
        self.setObjectName('parserInterface')