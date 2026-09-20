"""OKSS extensions to the shared Windows schedule page."""
from copy import deepcopy
import xml.etree.ElementTree as ET

from PySide6.QtWidgets import QWidget, QGridLayout, QHBoxLayout, QLabel
from qfluentwidgets import MessageBoxBase, SubtitleLabel, CheckBox, ComboBox, PushButton, LineEdit
from ok import og
from ok.util.windows_schedule import WindowsScheduleManager
from ok.ui.qt.tasks.ScheduleTaskTab import CreateScheduleTaskDialog, ModifyScheduleTaskDialog
from .tasks import STEPS, CustomDailyTask, DailyTask
from .schedule_profile import (CUSTOM_TASK, FLAG, CHOICES, default_profile, validate_profile,
                               token_from_description, decode_profile, description_for)
from .policy import NeedsReview
from .activity import CURRENT_EVENT_NAME


class ScheduleManager(WindowsScheduleManager):
    def _generate_task_xml(self, task_name, task_index, trigger_type, timeout_hours=0,
                           description="", start_hour=9, start_minute=0, auto_exit=True,
                           interval_days=0, interval_hours=0, task_identifier=None):
        xml = super()._generate_task_xml(task_name, task_index, trigger_type, timeout_hours,
                description, start_hour, start_minute, auto_exit, interval_days,
                interval_hours, task_identifier)
        if task_identifier != CUSTOM_TASK:
            return xml
        token = token_from_description(description)
        namespace = "http://schemas.microsoft.com/windows/2004/02/mit/task"
        ET.register_namespace("", namespace)
        root = ET.fromstring(xml)
        arguments = root.find(f".//{{{namespace}}}Arguments")
        arguments.text += f" {FLAG} {token}"
        return '<?xml version="1.0" encoding="UTF-16"?>\n' + ET.tostring(root, encoding="unicode")


class ProfileDialog(MessageBoxBase):
    def __init__(self, profile, parent):
        super().__init__(parent)
        self.viewLayout.addWidget(SubtitleLabel("此排程的執行項目", self))
        hint = QLabel("獨立儲存，不會改動首頁日課或其他排程。執行順序與日課相同。")
        hint.setWordWrap(True)
        self.viewLayout.addWidget(hint)
        self.activity_label = QLabel(f"目前活動：{CURRENT_EVENT_NAME}")
        self.viewLayout.addWidget(self.activity_label)
        actions = QHBoxLayout()
        self.checks = {}
        for title, checked in (("全選", True), ("清除", False)):
            button = PushButton(title)
            button.clicked.connect(lambda _=False, state=checked: self.select_all(state))
            actions.addWidget(button)
        actions.addStretch()
        self.viewLayout.addLayout(actions)
        tasks = QWidget(); grid = QGridLayout(tasks)
        grid.setContentsMargins(0, 0, 0, 0)
        for index, (name, _) in enumerate(STEPS):
            box = CheckBox(name)
            box.setChecked(name in profile["執行項目"])
            box.stateChanged.connect(self.update_options)
            self.checks[name] = box
            grid.addWidget(box, index // 3, index % 3)
        self.viewLayout.addWidget(tasks)
        settings = QWidget(); form = QGridLayout(settings)
        form.setContentsMargins(0, 0, 0, 0)
        self.options = {}
        for index, (key, values) in enumerate(CHOICES.items()):
            combo = ComboBox(); combo.addItems(values); combo.setCurrentText(profile[key])
            self.options[key] = combo
            form.addWidget(QLabel(key), index, 0); form.addWidget(combo, index, 1)
        self.viewLayout.addWidget(settings)
        self.yesButton.setText("使用這些設定")
        self.cancelButton.setText("取消")
        self.widget.setMinimumWidth(740)
        self.update_options()

    def select_all(self, state):
        for box in self.checks.values():
            box.setChecked(state)

    def update_options(self, *args):
        if not hasattr(self, "options"):
            return
        selected = {name for name, box in self.checks.items() if box.isChecked()}
        self.yesButton.setEnabled(bool(selected))
        for key, related in (("體力刷關", {"體力刷關"}), ("限時據點關卡", {"限時據點"}),
                             ("激戰委託關卡", {"激戰委託"})):
            self.options[key].setEnabled(bool(selected & related))

    def value(self):
        return validate_profile({"執行項目": [name for name, box in self.checks.items() if box.isChecked()],
                                 **{key: combo.currentText() for key, combo in self.options.items()}})


class ProfileControls:
    def add_profile_controls(self, profile, custom):
        self.profile = deepcopy(profile)
        self.custom_profile = custom
        self.profile_summary = QLabel()
        self.profile_summary.setWordWrap(True)
        self.profile_button = PushButton("設定執行項目…")
        self.profile_button.clicked.connect(self.edit_profile)
        self.viewLayout.addWidget(self.profile_summary)
        self.viewLayout.addWidget(self.profile_button)
        self.update_profile_controls()

    def update_profile_controls(self):
        self.profile_button.setVisible(self.custom_profile)
        names = self.profile["執行項目"]
        self.profile_summary.setText((f"此排程獨立執行 {len(names)} 項：" + "、".join(names)
            if names else "尚未選擇項目，請先設定執行項目。") if self.custom_profile else
            "執行時跟隨「星守日課」首頁的最新勾選與刷關設定。")
        self.yesButton.setEnabled(not self.custom_profile or bool(names))

    def edit_profile(self):
        dialog = ProfileDialog(self.profile, self)
        if dialog.exec():
            self.profile = dialog.value()
            self.update_profile_controls()


class CreateDialog(ProfileControls, CreateScheduleTaskDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        for index, task in enumerate(self.tasks):
            if type(task) is DailyTask:
                self.task_combo.setItemText(index, "跟隨日課設定（使用首頁勾選）")
            elif isinstance(task, CustomDailyTask):
                self.task_combo.setItemText(index, "自訂任務（每筆排程獨立設定）")
        self.schedule_name = LineEdit()
        self.schedule_name.setMaxLength(120)
        self.schedule_name.setPlaceholderText("排程名稱，例如：晚間好友點數（可留空）")
        self.viewLayout.addWidget(self.schedule_name)
        self.add_profile_controls(default_profile(), False)
        self.task_combo.currentIndexChanged.connect(self.select_mode)
        self.select_mode()

    def select_mode(self, *args):
        index = self.task_combo.currentIndex()
        self.custom_profile = 0 <= index < len(self.tasks) and isinstance(self.tasks[index], CustomDailyTask)
        self.update_profile_controls()

    def on_create(self):
        if self.custom_profile:
            self.schedule_description = description_for(self.profile)
        else:
            self.schedule_description = ""
        self.schedule_name_value = self.schedule_name.text().strip() or (
            "自訂任務" if self.custom_profile else "跟隨日課設定")
        super().on_create()


class ModifyDialog(ProfileControls, ModifyScheduleTaskDialog):
    def __init__(self, task_info, parent=None):
        super().__init__(task_info, parent)
        custom = task_info.task_identifier == CUSTOM_TASK
        if not task_info.task_identifier and 1 <= self.task_index <= len(og.executor.onetime_tasks):
            custom = isinstance(og.executor.onetime_tasks[self.task_index-1], CustomDailyTask)
        profile = default_profile()
        if custom:
            try:
                profile = decode_profile(token_from_description(task_info.description))
            except NeedsReview:
                pass  # Require a new selection; never substitute home settings.
        self.schedule_description = task_info.description
        self.add_profile_controls(profile, custom)

    def on_modify(self):
        if self.custom_profile:
            self.schedule_description = description_for(self.profile)
        super().on_modify()
