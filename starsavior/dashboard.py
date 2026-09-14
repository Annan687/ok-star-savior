"""Native Star Savior dashboard; all game operations stay in ok-py tasks."""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QLineEdit, QFrame, QProgressBar)

from .policy import FARM, TIMED
from .tasks import STEPS

ROOT = Path(__file__).resolve().parent.parent
GROUPS = {
    "領取與商店": [name for name, _ in STEPS[:6]],
    "刷關與挑戰": [name for name, _ in STEPS[6:13]],
    "任務與養成": [name for name, _ in STEPS[13:]],
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
        self.daily = next(t for t in og.executor.onetime_tasks if isinstance(t, DailyTask))
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
        return self.pending or self.daily.enabled or self.inspect.enabled

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
        if self.daily.enabled:
            self.daily.unpause() if self.daily.paused else self.daily.pause()

    def stop(self):
        # StartController owns connection attempts; stop is enabled after a
        # task is running, not while that controller is still connecting.
        for task in (self.daily, self.inspect):
            if task.enabled:
                task.disable()
                task.unpause()
        self.daily.info_set("執行狀態", "已停止")

    def snapshot(self):
        window = getattr(self.og.device_manager, "hwnd_window", None)
        connected = bool(window and window.exists)
        active = self.daily.enabled or self.inspect.enabled
        info = dict(self.daily.info)
        return {
            "connected": connected, "pending": self.pending, "busy": self.busy(),
            "active": active, "paused": self.daily.paused and self.daily.enabled,
            "daily_active": self.daily.enabled, "info": info,
            "inspection": dict(self.inspect.info), "error": self.error,
        }

    def connection(self):
        self.og.main_window.switchTo(self.og.main_window.start_tab)


class PreviewBackend:
    """Only for rendering this widget offline. Does not construct a game driver."""
    def __init__(self):
        self.values = {"執行項目": [n for n, _ in STEPS], "體力刷關": "不消耗體力",
                       "限時據點關卡": "略過", "活動名稱": "魔女的帷幕"}

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


class DailyPanel(QWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setObjectName("dailyPanel")
        self.setMinimumWidth(800)
        self.checks = {}
        self.row_status = {}
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
        brand.setPixmap(QIcon(str(ROOT / "assets/icon.svg")).pixmap(62, 62))
        hero_layout.addWidget(brand)
        heading = QVBoxLayout()
        heading.setSpacing(4)
        heading.addWidget(self.label("STAR SAVIOR  /  DAILY ASSISTANT", "eyebrow"))
        heading.addWidget(self.label("星守日課", "heroTitle"))
        heading.addWidget(self.label("照你的習慣，安排今天的日課。", "heroText"))
        hero_layout.addLayout(heading, 1)
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right.addWidget(self.label("OK-StarSavior · v0.2", "version"))
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

        columns = QHBoxLayout()
        columns.setSpacing(14)
        checklist, checklist_layout = self.card()
        checklist_layout.setSpacing(7)
        title_row = QHBoxLayout()
        title_row.addWidget(self.label("日課清單", "sectionTitle"))
        title_row.addStretch()
        all_button = self.button("全選", "small", lambda: self.select_all(True))
        none_button = self.button("清除", "small", lambda: self.select_all(False))
        self.settings_widgets.extend([all_button, none_button])
        title_row.addWidget(all_button)
        title_row.addWidget(none_button)
        checklist_layout.addLayout(title_row)
        selected = values.get("執行項目", [])
        for group, names in GROUPS.items():
            checklist_layout.addWidget(self.label(group, "groupTitle"))
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(3)
            for i, name in enumerate(names):
                row = QHBoxLayout()
                check = QCheckBox(name)
                check.setChecked(name in selected)
                check.setMinimumHeight(30)
                check.stateChanged.connect(self.persist)
                status = self.label("待執行", "rowStatus")
                status.setFixedWidth(42)
                row.addWidget(check, 1)
                row.addWidget(status)
                grid.addLayout(row, i//2, i%2)
                self.checks[name] = check
                self.row_status[name] = status
                self.settings_widgets.append(check)
            checklist_layout.addLayout(grid)
        checklist_layout.addStretch()
        columns.addWidget(checklist, 3)

        options, option_layout = self.card()
        options.setMinimumWidth(255)
        option_layout.addWidget(self.label("刷關安排", "sectionTitle"))
        self.farm = self.combo(option_layout, "體力要刷哪裡", ["不消耗體力", *FARM], values["體力刷關"])
        option_layout.addWidget(self.label("選定一關，MAX 使用現有體力。", "hint"))
        self.timed = self.combo(option_layout, "限時據點", ["略過", *TIMED], values["限時據點關卡"])
        option_layout.addWidget(self.label("每天剩餘的票券集中刷這一關。", "hint"))
        option_layout.addWidget(self.label("目前活動", "fieldLabel"))
        self.event_name = QLineEdit(values.get("活動名稱", "魔女的帷幕"))
        self.event_name.setPlaceholderText("輸入活動列表上的名稱")
        self.event_name.editingFinished.connect(self.persist)
        self.settings_widgets.append(self.event_name)
        option_layout.addWidget(self.event_name)
        option_layout.addStretch()
        option_layout.addWidget(self.label("設定自動儲存，下次開啟繼續沿用。", "hint"))
        columns.addWidget(options, 2)
        root.addLayout(columns)

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

        self.setStyleSheet(STYLE)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(750)
        self.refresh()

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
        widget.currentTextChanged.connect(self.persist)
        self.settings_widgets.append(widget)
        layout.addWidget(widget)
        return widget

    def selected(self):
        return [name for name, check in self.checks.items() if check.isChecked()]

    def persist(self, *args):
        if not hasattr(self, "event_name"):
            return
        self.backend.save({"執行項目": self.selected(), "體力刷關": self.farm.currentText(),
                           "限時據點關卡": self.timed.currentText(), "活動名稱": self.event_name.text().strip()})
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
        selected = self.selected()
        done, state = status_summary(info, selected)
        if data["pending"]:
            state = "正在連線"
        elif data["paused"]:
            state = "已暫停"
        elif data["active"]:
            state = "日課執行中" if data["daily_active"] else "畫面檢查中"
        elif data["error"]:
            state = "連線未完成"
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
        for name, status in self.row_status.items():
            full = str(info.get(name, ""))
            current = info.get("目前項目") == name and data["daily_active"]
            text = ("處理中" if current and not full else "已處理" if full.startswith("已執行：") else
                    "略過" if full.startswith("略過：") or name not in selected else
                    "需檢查" if full.startswith(("需校正", "執行失敗")) else "待執行")
            status.setText(text)
            status.setToolTip(full)
        error_rows = [str(info[n]) for n in selected if str(info.get(n, "")).startswith(("需校正", "執行失敗"))]
        if data["error"]:
            detail = "尚未連上遊戲。請開啟右上方「遊戲連線」選擇 StarSavior.exe。"
            self.detail.setToolTip(data["error"])
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
