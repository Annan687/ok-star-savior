from PySide6.QtCore import QObject, QTimer


class Globals(QObject):
    def __init__(self, exit_event):
        super().__init__()

    def on_show_main_window(self, window):
        from .ui import DailyTab
        home = window.findChild(DailyTab)
        if home:
            window.first_task_tab = home
            QTimer.singleShot(0, lambda: window.switchTo(home))
