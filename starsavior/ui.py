from qfluentwidgets import FluentIcon, NavigationItemPosition
from ok.ui.qt.widget.Tab import Tab
from .dashboard import DailyPanel, RuntimeBackend


class DailyTab(Tab):
    name = "星守日課"
    icon = FluentIcon.CHECKBOX
    add_after_default_tabs = False
    position = NavigationItemPosition.SCROLL

    def __init__(self):
        super().__init__()
        self.setObjectName("starSaviorHome")
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.panel = DailyPanel(RuntimeBackend())
        self.add_widget(self.panel)
