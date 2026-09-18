from PySide6.QtCore import QObject, QTimer


class Globals(QObject):
    def __init__(self, exit_event):
        super().__init__()
        self.window = None
        self._case_signals_connected = False

    def on_show_main_window(self, window):
        from ok.ui.qt.Communicate import communicate
        self.window = window
        if not self._case_signals_connected:
            communicate.task.connect(self.sync_case_controls)
            communicate.task_list_updated.connect(self.sync_case_controls)
            self._case_signals_connected = True
        self.sync_case_controls()
        from .ui import DailyTab
        home = window.findChild(DailyTab)
        if home:
            window.first_task_tab = home
            QTimer.singleShot(0, lambda: window.switchTo(home))

    def sync_case_controls(self, *args):
        if self.window is not None:
            lock_case_controls(self.window)


def lock_case_controls(window):
    """Keep the embedded helper's options fixed for its whole session."""
    from ok.ui.qt.tasks.TaskCard import TaskCard
    from .case_task import CaseFilesTask
    for card in window.findChildren(TaskCard):
        if isinstance(card.task, CaseFilesTask):
            editable = not (card.task.enabled or card.task.running)
            for widget in card.config_widgets:
                widget.setEnabled(editable)
            if card.reset_config is not None:
                card.reset_config.setEnabled(editable)
