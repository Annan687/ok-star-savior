"""Framework background input with local, explicit delivery diagnostics."""
import json
import os
import sys
import time
from pathlib import Path

import win32api
import win32con
import win32gui
import win32process
import win32security

from ok.device.interaction_methods.post_message import PostMessageInteraction
from ok.device.interaction_methods.genshin import GenshinInteraction
from .policy import NeedsReview


def input_context(hwnd):
    """Observe focus and physical cursor without moving or activating anything."""
    try:
        foreground = win32gui.GetForegroundWindow()
        cursor = win32api.GetCursorPos()
        return {"foreground_hwnd": foreground, "target_foreground": foreground == hwnd,
                "cursor_screen": list(cursor),
                "cursor_client": list(win32gui.ScreenToClient(hwnd, cursor))}
    except Exception as error:
        return {"input_context_error": str(error)}


def process_privileges(pid):
    process = token = None
    try:
        process = win32api.OpenProcess(0x1000, False, pid)
        token = win32security.OpenProcessToken(process, win32con.TOKEN_QUERY)
        integrity = win32security.GetTokenInformation(token, win32security.TokenIntegrityLevel)
        return {"pid": pid,
                "elevated": bool(win32security.GetTokenInformation(token, win32security.TokenElevation)),
                "integrity": win32security.ConvertSidToStringSid(integrity[0])}
    except Exception as error:
        return {"pid": pid, "query_error": str(error)}
    finally:
        if token is not None:
            token.Close()
        if process is not None:
            process.Close()


class CheckedPostMessage(PostMessageInteraction):
    """Keep the framework's message sequence; never fall back to real mouse input."""
    trace_path = None

    def begin_trace(self, folder):
        import ok
        self.trace_path = Path(folder) / "input-trace.jsonl"
        hwnd = self.hwnd_window.hwnd
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        self.write_trace({"event": "start", "driver": type(self).__name__,
                          "python": sys.executable, "framework": ok.__file__,
                          "assistant": process_privileges(os.getpid()),
                          "game": process_privileges(pid), "game_hwnd": hwnd,
                          "client_rect": win32gui.GetClientRect(hwnd),
                          "client_origin": win32gui.ClientToScreen(hwnd, (0, 0)),
                          "frame_size": [self.capture.width, self.capture.height],
                          "game_foreground": self.hwnd_window.is_foreground()})

    def write_trace(self, event):
        if self.trace_path is not None:
            with self.trace_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps({"time": time.time(), **event}, ensure_ascii=False) + "\n")

    def post(self, message, wParam=0, lParam=0, hwnd=None):
        target = self.hwnd if hwnd is None else hwnd
        event = {"event": "message", "hwnd": target, "message": message,
                 "wparam": wParam, "lparam": lParam, **input_context(target)}
        if message in (win32con.WM_MOUSEMOVE, win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP):
            event["client_point"] = [lParam & 0xffff, (lParam >> 16) & 0xffff]
        try:
            win32gui.PostMessage(target, message, wParam, lParam)
        except Exception as error:
            code = getattr(error, "winerror", None)
            if code is None and error.args:
                code = error.args[0]
            event.update(queued=False, error_code=code, error=str(error))
            self.write_trace(event)
            raise NeedsReview(f"Windows 拒絕背景輸入（錯誤 {code}）：{error}") from error
        event["queued"] = True  # Accepted by Windows; not proof the game handled it.
        self.write_trace(event)


class CursorPostMessage(CheckedPostMessage):
    """Experimental clicks: sync physical cursor without bringing the game forward."""

    def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01, move=True, key="left"):
        if x < 0 or y < 0:
            raise NeedsReview("游標同步測試需要明確點擊座標")
        original = win32api.GetCursorPos()
        base = self.hwnd_window.top_hwnd or self.hwnd_window.hwnd
        local = self.hwnd_window.get_top_window_cords(x, y)
        target = win32gui.ClientToScreen(base, (int(local[0]), int(local[1])))
        self.write_trace({"event": "cursor_sync_begin", "original": original,
                          "target": target, **input_context(base)})
        try:
            win32api.SetCursorPos(target)
            time.sleep(0.035)
            super().click(x, y, move_back=False, name=name, down_time=down_time, move=move, key=key)
            # PostMessage is asynchronous; allow the game to consume button-up.
            time.sleep(0.05)
        finally:
            win32api.SetCursorPos(original)
            self.write_trace({"event": "cursor_sync_end", **input_context(base)})


class CheckedGenshin(GenshinInteraction):
    """Framework Genshin experiment with diagnostics and exception-safe cleanup."""
    trace_path = None
    begin_trace = CheckedPostMessage.begin_trace
    write_trace = CheckedPostMessage.write_trace
    post = CheckedPostMessage.post

    def block_input(self):
        result = self.user32.BlockInput(True)
        self.write_trace({"event": "block_input", "succeeded": bool(result)})

    def operate(self, fun, block=False):
        original = win32api.GetCursorPos()
        self.write_trace({"event": "genshin_begin", **input_context(self.hwnd)})
        try:
            return super().operate(fun, block)
        finally:
            try:
                win32api.SetCursorPos(original)
            finally:
                if block:
                    self.unblock_input()
            self.write_trace({"event": "genshin_end", **input_context(self.hwnd)})

    def on_destroy(self):
        # The framework implementation brings the game forward during teardown.
        self.hwnd_window.to_handle_mute = True
