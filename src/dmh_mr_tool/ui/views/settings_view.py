from ui.views.base_view import BaseInterface


class SettingsInterface(BaseInterface):
    def __init__(self, parent=None):
        super().__init__(title="SettingInterface", subtitle="SettingInterface", parent=parent)
        self.setObjectName('settingInterface')