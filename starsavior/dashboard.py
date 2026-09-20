"""Native Star Savior dashboard; all game operations stay in ok-py tasks."""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QToolButton,
    QLabel, QPushButton, QCheckBox, QComboBox, QFrame, QProgressBar)

from .policy import FARM, TIMED
from .tasks import STEPS
from .events import ONSLAUGHT
from .activity import CURRENT_EVENT_NAME

ROOT = Path(__file__).resolve().parent.parent
GROUPS = {
    "領取與商店": [name for name, _ in STEPS[:6]],
    "刷關與挑戰": [name for name, _ in STEPS[6:12]],
    "活動": [name for name, _ in STEPS[12:16]],
    "任務與養成": [name for name, _ in STEPS[16:]],
}


def status_summary(info, selected):
    handled = sum(str(info.get(name, "")).startswith(("已執行：", "略過：")) for name in selected)
    state = str(info.get("執行狀態", "尚未開始"))
    return handled, state


class RuntimeBackend:
    """Use the framework's own start/pause/stop and persistent task config."""
    def __init__(self):
        from ok import og
        from .tasks import DailyTask, InspectTask
        from ok.ui.qt.Communicate import communicate
        self.og = og
        self.daily = next(t for t in og.executor.onetime_tasks if type(t) is DailyTask)
        self.inspect = next(t for t in og.executor.onetime_tasks if isinstance(t, InspectTask))
        self.pending = False
        self.error = ""
        communicate.starting_emulator.connect(self.on_start)

    def on_start(self, done, error, seconds_left):
        self.pending = not done
        if error:
            self.error = str(error)

    def settings(self):
        return dict(self.daily.config)

    def save(self, settings):
        if self.busy():
            raise RuntimeError("請先停止日課再更改設定")
        changed = any(self.daily.config.get(key) != value for key, value in settings.items())
        for key, value in settings.items():
            self.daily.config[key] = value
        if changed:
            self.daily.info_clear()

    def busy(self):
        return self.pending or self.daily.enabled or self.inspect.enabled or bool(self.other_task())

    def other_task(self):
        executor = getattr(getattr(self, "og", None), "executor", None)
        return next((task for task in getattr(executor, "onetime_tasks", ())
                     if task not in (self.daily, self.inspect) and (task.enabled or task.running)), None)

    def start(self, inspect=False):
        if self.busy():
            return
        self.error = ""
        from .config import config
        if config["windows"]["interaction"] == "Pynput":
            window = getattr(getattr(self.og, "device_manager", None), "hwnd_window", None)
            if window is not None and window.exists and not window.bring_to_front():
                self.error = "無法切到遊戲前台，請先點選遊戲視窗後再開始。"
                return
        self.pending = True
        self.og.app.start_controller.start(self.inspect if inspect else self.daily)

    def pause(self):
        task = self.running_daily()
        if task.enabled:
            task.unpause() if task.paused else task.pause()

    def running_daily(self):
        from .tasks import CustomDailyTask
        other = self.other_task()
        return other if isinstance(other, CustomDailyTask) else self.daily

    def stop(self):
        # StartController owns connection attempts; stop is enabled after a
        # task is running, not while that controller is still connecting.
        daily = self.running_daily()
        for task in (daily, self.inspect):
            if task.enabled:
                task.disable()
                task.unpause()
        daily.info_set("執行狀態", "已停止")

    def snapshot(self):
        window = getattr(self.og.device_manager, "hwnd_window", None)
        connected = bool(window and window.exists)
        daily = self.running_daily()
        active = daily.enabled or self.inspect.enabled
        info = dict(daily.info)
        other = self.other_task()
        return {
            "connected": connected, "pending": self.pending, "busy": self.busy(),
            "active": active, "paused": daily.paused and daily.enabled,
            "daily_active": daily.enabled, "info": info,
            "custom_active": daily is not self.daily,
            "runtime_selected": list(daily.config.get("執行項目", [])) if daily is not self.daily else None,
            "inspection": dict(self.inspect.info), "error": self.error,
            "other_task": other.name if other else "",
        }

    def connection(self):
        self.og.main_window.switchTo(self.og.main_window.start_tab)


class PreviewBackend:
    """Only for rendering this widget offline. Does not construct a game driver."""
    def __init__(self):
        self.values = {"執行項目": [n for n, _ in STEPS], "體力刷關": "不消耗體力",
                       "限時據點關卡": "略過", "激戰委託關卡": "略過",
                       "Exit After Task": False}

    def settings(self):
        return dict(self.values)

    def save(self, settings):
        self.values.update(settings)

    def snapshot(self):
        return {"connected": False, "pending": False, "busy": False, "active": False,
                "paused": False, "daily_active": False, "info": {}, "inspection": {},
                "error": "", "preview": True}

    def start(self, inspect=False):
        pass

    def pause(self):
        pass

    def stop(self):
        pass

    def connection(self):
        pass


class TaskSection(QFrame):
    """Folding is presentation only; it never changes task selections."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("taskSection")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(10, 5, 18, 5)
        self.toggle = QToolButton()
        self.toggle.setObjectName("sectionToggle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.summary = QLabel()
        self.summary.setObjectName("sectionSummary")
        header.addWidget(self.toggle, 1)
        header.addWidget(self.summary)
        layout.addLayout(header)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(18, 0, 18, 12)
        self.body_layout.setSpacing(0)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self.set_expanded)
        self.set_expanded(False)

    def set_expanded(self, expanded):
        self.toggle.setChecked(expanded)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle.setAccessibleName(f"{'折疊' if expanded else '展開'}{self.toggle.text()}")
        self.body.setVisible(expanded)


class DailyPanel(QWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setObjectName("dailyPanel")
        self.setMinimumWidth(800)
        self.checks = {}
        self.row_status = {}
        self.sections = {}
        self.task_options = {}
        self.event_labels = []
        self.settings_widgets = []
        values = backend.settings()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        brand = QLabel()
        brand.setPixmap(QIcon(str(ROOT / "assets/icon.png")).pixmap(62, 62))
        hero_layout.addWidget(brand)
        heading = QVBoxLayout()
        heading.setSpacing(4)
        heading.addWidget(self.label("STAR SAVIOR  /  DAILY ASSISTANT", "eyebrow"))
        heading.addWidget(self.label("星守日課", "heroTitle"))
        heading.addWidget(self.label("照你的習慣，安排今天的日課。", "heroText"))
        hero_layout.addLayout(heading, 1)
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right.addWidget(self.label("OK-StarSavior · v0.2.3", "version"))
        self.connection_badge = self.label("等待遊戲連線", "connectionBadge")
        right.addWidget(self.connection_badge)
        hero_layout.addLayout(right)
        root.addWidget(hero)

        toolbar = QHBoxLayout()
        self.start_button = self.button("開始日課", "primary", lambda: self.start(False))
        self.inspect_button = self.button("檢查遊戲畫面", "secondary", lambda: self.start(True))
        self.pause_button = self.button("暫停", "secondary", self.backend.pause)
        self.stop_button = self.button("停止", "stop", self.backend.stop)
        self.device_button = self.button("遊戲連線", "secondary", self.backend.connection)
        for button in (self.start_button, self.inspect_button, self.pause_button, self.stop_button):
            toolbar.addWidget(button)
        toolbar.addStretch()
        toolbar.addWidget(self.device_button)
        root.addLayout(toolbar)

        metrics = QHBoxLayout()
        self.selected_value = self.add_metric(metrics, "今日安排", f"{len(STEPS)} 項")
        self.done_value = self.add_metric(metrics, "本輪已處理", f"0 / {len(STEPS)}")
        self.state_value = self.add_metric(metrics, "執行狀態", "尚未開始")
        root.addLayout(metrics)

        title_row = QHBoxLayout()
        title_row.addWidget(self.label("日課清單", "sectionTitle"))
        title_row.addStretch()
        all_button = self.button("全選", "small", lambda: self.select_all(True))
        none_button = self.button("清除", "small", lambda: self.select_all(False))
        self.settings_widgets.extend([all_button, none_button])
        title_row.addWidget(all_button)
        title_row.addWidget(none_button)
        title_row.addWidget(self.button("全部展開", "small", lambda: self.expand_all(True)))
        title_row.addWidget(self.button("全部折疊", "small", lambda: self.expand_all(False)))
        root.addLayout(title_row)
        selected = values.get("執行項目", [])
        for group, names in GROUPS.items():
            section = TaskSection(group)
            self.sections[group] = section
            root.addWidget(section)
            for name in names:
                item = QFrame()
                item.setObjectName("taskItem")
                item_layout = QVBoxLayout(item)
                item_layout.setContentsMargins(6, 10, 6, 10)
                item_layout.setSpacing(6)
                row = QHBoxLayout()
                check = QCheckBox(name)
                check.setChecked(name in selected)
                check.setMinimumHeight(28)
                check.stateChanged.connect(self.persist)
                status = self.label("待執行", "rowStatus")
                status.setFixedWidth(54)
                status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                row.addWidget(check, 1)
                row.addWidget(status)
                item_layout.addLayout(row)
                self.checks[name] = check
                self.row_status[name] = status
                self.settings_widgets.append(check)
                self.add_task_options(name, item_layout, values)
                section.body_layout.addWidget(item)

        options, option_layout = self.card()
        option_layout.addWidget(self.label("執行設定", "sectionTitle"))
        self.exit_after = QCheckBox("完成後關閉遊戲與 OKSS")
        self.exit_after.setChecked(bool(values.get("Exit After Task", False)))
        self.exit_after.toggled.connect(self.persist)
        self.settings_widgets.append(self.exit_after)
        option_layout.addWidget(self.exit_after)
        schedule_hint = self.label("每日時間請至左側「計劃任務」設定。電腦需開機、Windows 已登入且未鎖定。", "hint")
        schedule_hint.setWordWrap(True)
        option_layout.addWidget(schedule_hint)
        option_layout.addWidget(self.label("設定自動儲存，下次開啟繼續沿用。", "hint"))
        root.addWidget(options)

        progress_card, progress_layout = self.card()
        progress_layout.setSpacing(8)
        progress_header = QHBoxLayout()
        progress_header.addWidget(self.label("本輪進度", "sectionTitle"))
        progress_header.addStretch()
        progress_header.addWidget(self.button("執行紀錄 ↗", "small", lambda: self.open_local("runs")))
        progress_header.addWidget(self.button("使用說明 ↗", "small", lambda: self.open_local("README.md")))
        progress_layout.addLayout(progress_header)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        progress_layout.addWidget(self.progress)
        self.detail = self.label("先檢查遊戲畫面，再開始本日安排。", "detail")
        self.detail.setWordWrap(True)
        progress_layout.addWidget(self.detail)
        root.addWidget(progress_card)
        note = self.label("前台模式 · 執行時會切到遊戲並使用滑鼠；整輪日課仍待實機校正。", "footer")
        note.setWordWrap(True)
        root.addWidget(note)
        root.addStretch()

        self.setStyleSheet(STYLE)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(750)
        self.refresh()

    def add_task_options(self, name, layout, values):
        if name not in ("體力刷關", "限時據點", "激戰委託", "活動襲擊", "活動任務", "環形鏈路"):
            return
        container = QFrame()
        container.setObjectName("taskOptions")
        inner = QVBoxLayout(container)
        inner.setContentsMargins(24, 0, 14, 10)
        inner.setSpacing(7)
        if name == "體力刷關":
            self.farm = self.combo(inner, "體力要刷哪裡", ["不消耗體力", *FARM], values["體力刷關"])
            hint = "選定一關，MAX 使用現有體力。"
        elif name == "限時據點":
            self.timed = self.combo(inner, "限時據點關卡", ["略過", *TIMED], values["限時據點關卡"])
            hint = "每天剩餘的票券集中刷這一關。"
        elif name == "激戰委託":
            self.onslaught = self.combo(inner, "激戰委託關卡", ["略過", *ONSLAUGHT], values.get("激戰委託關卡", "略過"))
            hint = "三種關卡共用免費票；選定後 MAX 用完剩餘票券。"
        elif name in ("活動襲擊", "活動任務"):
            inner.addWidget(self.label("目前活動", "fieldLabel"))
            label = self.label(CURRENT_EVENT_NAME, "detail")
            label.setWordWrap(True)
            self.event_labels.append(label)
            inner.addWidget(label)
            hint = ("MAX 用完剩餘免費票；活動任務可另外勾選。" if name == "活動襲擊"
                    else "只領取活動任務與點數獎勵，不進行襲擊掃蕩。與活動襲擊共用活動名稱。")
        else:
            hint = "領取環形鏈路任務票券後，全部抽取。"
        label = self.label(hint, "hint")
        label.setWordWrap(True)
        inner.addWidget(label)
        layout.addWidget(container)
        self.task_options[name] = container
        container.setVisible(self.checks[name].isChecked())

    def expand_all(self, expanded):
        for section in self.sections.values():
            section.set_expanded(expanded)

    @staticmethod
    def label(text, name):
        result = QLabel(text)
        result.setObjectName(name)
        return result

    @staticmethod
    def card():
        widget = QFrame()
        widget.setObjectName("card")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        return widget, layout

    @staticmethod
    def button(text, name, callback):
        button = QPushButton(text)
        button.setObjectName(name)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def add_metric(self, layout, title, value):
        card, inner = self.card()
        inner.setSpacing(4)
        inner.addWidget(self.label(title, "hint"))
        output = self.label(value, "metric")
        inner.addWidget(output)
        layout.addWidget(card, 1)
        return output

    def combo(self, layout, label, options, selected):
        layout.addWidget(self.label(label, "fieldLabel"))
        widget = QComboBox()
        widget.addItems(options)
        widget.setCurrentText(selected)
        widget.setMinimumWidth(210)
        widget.setMaximumWidth(480)
        widget.currentTextChanged.connect(self.persist)
        self.settings_widgets.append(widget)
        layout.addWidget(widget)
        return widget

    def selected(self):
        return [name for name, check in self.checks.items() if check.isChecked()]

    def persist(self, *args):
        if not hasattr(self, "exit_after"):
            return
        self.backend.save({"執行項目": self.selected(), "體力刷關": self.farm.currentText(),
                           "限時據點關卡": self.timed.currentText(),
                           "激戰委託關卡": self.onslaught.currentText(),
                           "Exit After Task": self.exit_after.isChecked()})
        self.refresh()

    def select_all(self, selected):
        for check in self.checks.values():
            check.blockSignals(True)
            check.setChecked(selected)
            check.blockSignals(False)
        self.persist()

    def start(self, inspect):
        self.persist()
        self.backend.start(inspect=inspect)
        self.refresh()

    def open_local(self, name):
        path = ROOT / name
        if name == "runs":
            path.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def refresh(self):
        data = self.backend.snapshot()
        info = data["info"]
        selected = data.get("runtime_selected") if data.get("custom_active") else self.selected()
        done, state = status_summary(info, selected)
        if data["pending"]:
            state = "正在連線"
        elif data["paused"]:
            state = "已暫停"
        elif data["active"]:
            state = "自訂排程執行中" if data.get("custom_active") else "日課執行中" if data["daily_active"] else "畫面檢查中"
        elif data["error"]:
            state = "連線未完成"
        elif data.get("other_task"):
            state = f"{data['other_task']}執行中"
        self.selected_value.setText(f"{len(selected)} 項")
        self.done_value.setText(f"{done} / {len(selected)}")
        self.state_value.setText(state)
        self.connection_badge.setText("畫面預覽 · 未連線" if data.get("preview") else
                                      "已找到遊戲視窗" if data["connected"] else "等待遊戲連線")
        self.progress.setRange(0, max(1, len(selected)))
        self.progress.setValue(done)
        self.start_button.setEnabled(not data["busy"] and bool(selected) and not data.get("preview"))
        self.inspect_button.setEnabled(not data["busy"] and not data.get("preview"))
        self.pause_button.setEnabled(data["daily_active"] and not data["pending"])
        self.pause_button.setText("繼續" if data["paused"] else "暫停")
        self.stop_button.setEnabled(data["active"] and not data["pending"])
        for widget in self.settings_widgets:
            widget.setEnabled(not data["busy"])
        for name, options in self.task_options.items():
            options.setVisible(self.checks[name].isChecked())
        for name, status in self.row_status.items():
            full = str(info.get(name, ""))
            current = info.get("目前項目") == name and data["daily_active"]
            text = ("處理中" if current and not full else "已處理" if full.startswith("已執行：") else
                    "略過" if full.startswith("略過：") or name not in selected else
                    "需檢查" if full.startswith(("需校正", "執行失敗")) else "待執行")
            status.setText(text)
            status.setToolTip(full)
        for group, section in self.sections.items():
            names = [name for name in GROUPS[group] if name in selected]
            handled, _ = status_summary(info, names)
            attention = any(str(info.get(name, "")).startswith(("需校正", "執行失敗")) for name in names)
            running = info.get("目前項目") in names and data["daily_active"]
            suffix = " · 需檢查" if attention else " · 處理中" if running else ""
            section.summary.setText(f"已選 {len(names)} / {len(GROUPS[group])} · 已處理 {handled}{suffix}")
        error_rows = [str(info[n]) for n in selected if str(info.get(n, "")).startswith(("需校正", "執行失敗"))]
        if data["error"]:
            detail = "尚未連上遊戲。請開啟右上方「遊戲連線」選擇 StarSavior.exe。"
            self.detail.setToolTip(data["error"])
        elif data.get("other_task"):
            detail = f"{data['other_task']}正在執行，請至左側「任務」查看進度或停止。"
        elif error_rows:
            detail = error_rows[0]
        elif data["active"]:
            detail = f"目前項目：{info.get('目前項目', '正在檢查遊戲畫面')}"
        elif info.get("執行狀態"):
            detail = f"{info['執行狀態']}。各項結果可移到清單狀態上查看，完整紀錄保存在本機。"
        elif data["inspection"]:
            detail = f"畫面檢查：{data['inspection'].get('畫面', '請查看執行紀錄')} · {data['inspection'].get('擷取尺寸', '')}"
        else:
            detail = "先檢查遊戲畫面，再開始本日安排。"
        self.detail.setText(detail)


STYLE = """
QWidget#dailyPanel {background:#f3f4f6; color:#263349; font-family:'Microsoft JhengHei UI'; font-size:13px;}
QFrame#hero {background:#172a43; border:1px solid #20364f; border-radius:14px;}
QLabel {color:#263349; background:transparent;}
QLabel#eyebrow {color:#c4ad7a; font-size:10px; letter-spacing:2px;}
QLabel#heroTitle {color:#ffffff; font-size:29px; font-weight:700;}
QLabel#heroText {color:#bac9dc; font-size:12px;}
QLabel#version {color:#b8c6d7; font-size:11px;}
QLabel#connectionBadge {color:#f1d497; background:#2a3d55; padding:7px 12px; border-radius:12px; font-size:11px;}
QFrame#card {background:white; border:1px solid #e3e7ee; border-radius:10px;}
QFrame#taskSection {background:white; border:1px solid #e3e7ee; border-radius:10px;}
QToolButton#sectionToggle {background:transparent; color:#263349; border:none; text-align:left; padding:10px 8px; font-size:14px; font-weight:600;}
QToolButton#sectionToggle:hover {background:#edf2f8; border-radius:6px;}
QLabel#sectionSummary {color:#768398; font-size:11px;}
QFrame#taskItem {border:none; border-top:1px solid #edf0f5;}
QFrame#taskOptions {background:#f7f9fc; border:none; border-radius:6px;}
QLabel#sectionTitle {font-size:15px; font-weight:700;}
QLabel#groupTitle {color:#758499; font-size:11px; margin-top:7px;}
QLabel#fieldLabel {font-size:12px; font-weight:600; margin-top:8px;}
QLabel#hint, QLabel#footer {color:#768398; font-size:11px;}
QLabel#metric {font-size:21px; font-weight:700;}
QLabel#rowStatus {color:#8c99ab; font-size:10px;}
QLabel#detail {font-size:12px; color:#617188;}
QPushButton {padding:9px 16px; border-radius:7px; font-family:'Microsoft JhengHei UI'; font-size:12px;}
QPushButton#primary {background:#253f61; color:white; border:1px solid #253f61; font-weight:600;}
QPushButton#primary:hover {background:#34577f;}
QPushButton#secondary {background:white; color:#344861; border:1px solid #dce2eb;}
QPushButton#secondary:hover {background:#eaf0f7;}
QPushButton#stop {background:#fff5f3; color:#af594a; border:1px solid #eed9d3;}
QPushButton#small {background:transparent; color:#687b93; border:none; padding:3px 5px; font-size:11px;}
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#secondary:disabled, QPushButton#stop:disabled {background:#e6e9ef; color:#9aa5b6; border:1px solid #e0e4eb;}
QCheckBox {spacing:6px; font-size:12px; color:#34465d;}
QCheckBox::indicator {width:14px; height:14px; border:1px solid #bdc7d5; border-radius:4px; background:white;}
QCheckBox::indicator:checked {background:#34577b; border:1px solid #34577b; image:url(assets/check.svg);}
QCheckBox:disabled {color:#9aa5b6;}
QComboBox, QLineEdit {background:#f9fafc; color:#34465d; border:1px solid #dce2eb; border-radius:6px; padding:8px; font-size:12px;}
QComboBox QAbstractItemView {background:white; color:#34465d; selection-background-color:#e7edf5;}
QProgressBar {border:none; background:#edf0f5; border-radius:3px;}
QProgressBar::chunk {background:#c4a366; border-radius:3px;}
"""
