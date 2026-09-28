"""Non-activating, click-through Qt overlay. All widgets live on the GUI thread."""
from PySide6.QtCore import Qt, QTimer, QRectF, QLineF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget, QApplication
from opencc import OpenCC
import re
import unicodedata

from .model import STORE

_simplify = OpenCC('t2s')
_traditional = OpenCC('s2t')


def display_text(value, language='繁體'):
    # Omit ownership/class labels in both measurement and painting; retain the
    # source and meaningful parentheses such as duration, discount and caps.
    value = re.sub(r'[（(][^（）()\n]*(?:专用|專用|专属|專屬)[）)]', '', value)
    value = value.replace('实力', '力量').replace('實力', '力量')
    value = value.replace('命中', '专注').replace('命抗', '保护')
    return (_simplify if language == '简体' else _traditional).convert(value)


def wrapped_lines(hint, card_width, scale=1, language='繁體'):
    # Explicit wrapping is shared by sizing and painting, so long success/failure
    # branches cannot silently disappear outside a fixed-height card.
    units = max(12, int((card_width - 24*scale)/(8*scale)))
    result = []
    lines = visible_effect_lines(hint.lines)
    for paragraph in [f'{hint.index}  {lines[0]}', *lines[1:]]:
        line, count = '', 0
        for char in display_text(paragraph, language):
            size = 2 if unicodedata.east_asian_width(char) in 'WF' else 1
            if char == '\n' or count + size > units:
                result.append(line)
                line, count = '', 0
            if char != '\n':
                line += char
                count += size
        if line:
            result.append(line)
    return result


def visible_effect_lines(lines):
    """Hide coin costs only; retain rewards, other costs and source data."""
    visible = []
    for line in lines:
        parts = []
        for part in re.split('[｜|]', line):
            compact = re.sub(r'\s+', '', _simplify.convert(part))
            if re.fullmatch(r'(?:(?:消耗|消费)(?:旧硬币|硬币|金币)\d+|(?:旧硬币|硬币|金币)[-−]\d+)', compact):
                continue
            if part.strip():
                parts.append(part.strip())
        if parts:
            visible.append('｜'.join(parts))
    return visible or ['无额外效果']


def hint_rectangles(advice, width, height):
    if not advice or not advice.hints:
        return []
    if advice.column_titles:
        return comparison_rectangles(advice, width, height)
    right = min(h.x for h in advice.hints) - .075
    card_width = min(.29, right-.025)*width
    scale = width/1600
    if all(len(wrapped_lines(h, card_width, scale)) <= 2 for h in advice.hints):
        return [QRectF(right*width-card_width, h.y*height-27*scale,
                       card_width, 54*scale) for h in advice.hints]
    card_width = min(.40, right-.025)*width
    heights = [max(54*scale, len(wrapped_lines(h, card_width, scale))*20*scale+12*scale)
               for h in advice.hints]
    total = sum(heights) + 8*scale*(len(heights)-1)
    y = max(.14*height, min(sum(h.y for h in advice.hints)/len(heights)*height-total/2,
                           .88*height-total))
    rectangles = []
    for card_height in heights:
        rectangles.append(QRectF(right*width-card_width, y, card_width, card_height))
        y += card_height + 8*scale
    return rectangles


def comparison_rectangles(advice, width, height):
    """Two labeled columns with matching option rows and enough room for text."""
    scale = width/1600
    right = (min(h.x for h in advice.hints) - .075)*width
    left, gap = .025*width, 12*scale
    column_width = (right-left-gap)/2
    indices = sorted({h.index for h in advice.hints})
    heights = {i: max(54*scale, max(len(wrapped_lines(h, column_width, scale))
                                   for h in advice.hints if h.index == i)*20*scale+12*scale)
               for i in indices}
    total = sum(heights.values()) + (len(indices)-1)*8*scale
    centers = [h.y*height for h in advice.hints if h.column == 0]
    y = max(.14*height+32*scale, min(sum(centers)/len(centers)-total/2,
                                     .88*height-total))
    rows = {}
    for i in indices:
        rows[i] = y
        y += heights[i]+8*scale
    return [QRectF(left+h.column*(column_width+gap), rows[h.index],
                   column_width, heights[h.index]) for h in advice.hints]


def paint_advice(painter, advice, width, height, opacity=80, language='繁體'):
    if advice is None:
        return
    scale = width/1600
    painter.setRenderHint(QPainter.Antialiasing)
    font = QFont('Microsoft JhengHei')
    font.setPixelSize(max(11, round(15*scale)))
    painter.setFont(font)
    def text(value):
        return display_text(value, language)
    def card(rect, lines, accent='#92d8f8'):
        painter.setPen(QPen(QColor(accent), max(1, scale)))
        painter.setBrush(QColor(17, 27, 43, round(255*opacity/100)))
        painter.drawRoundedRect(rect, 7*scale, 7*scale)
        painter.setPen(QColor('#f6f8fc'))
        body = rect.adjusted(11*scale, 5*scale, -9*scale, -5*scale)
        painter.drawText(body, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, text('\n'.join(lines)))
    rectangles = hint_rectangles(advice, width, height)
    if not rectangles:
        card(QRectF(.36*width, .43*height, .29*width, 50*scale), [advice.status], '#cabd97')
        return
    for column, title in enumerate(advice.column_titles):
        first = next(rect for hint, rect in zip(advice.hints, rectangles) if hint.column == column)
        card(QRectF(first.x(), first.y()-32*scale, first.width(), 27*scale), [title])
    for hint, rect in zip(advice.hints, rectangles):
        if (not advice.column_titles or hint.column == len(advice.column_titles)-1) and abs(rect.center().y() - hint.y*height) > 3*scale:
            painter.setPen(QPen(QColor('#92d8f8'), max(1, scale)))
            painter.drawLine(QLineF(rect.right(), rect.center().y(),
                                   (hint.x-.015)*width, hint.y*height))
        card(rect, wrapped_lines(hint, rect.width(), scale, language))
    last = rectangles[-1]
    painter.setPen(QColor('#e1e9f5'))
    painter.drawText(QRectF(last.x(), last.bottom()+5*scale, last.width(), 23*scale),
                     Qt.AlignLeft | Qt.AlignVCenter, text(advice.warning or '效果依原困難表 · 體力＝跑馬體力'))


def game_bounds(hwnd):
    import win32gui
    import pywintypes
    try:
        return _game_bounds(hwnd, win32gui)
    except pywintypes.error:
        return None  # The game may close between the window checks.


def _game_bounds(hwnd, win32gui):
    if not hwnd or not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
        return None
    if not win32gui.IsWindowVisible(hwnd):
        return None
    if win32gui.GetAncestor(win32gui.GetForegroundWindow(), 2) != win32gui.GetAncestor(hwnd, 2):
        return None
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    _, _, width, height = win32gui.GetClientRect(hwnd)
    return (left, top, width, height) if width > 0 and height > 0 else None


class JourneyOverlay(QWidget):
    def __init__(self, owner=None):
        # An owned Tool window is hidden when OKSS is minimized on Windows.
        # Keep this independent so users can minimize OKSS while playing.
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        if owner is not None:
            owner.destroyed.connect(self.close)
        QApplication.instance().aboutToQuit.connect(self.close)
        self.setObjectName('journeyAdviceOverlay')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.payload = None
        self._bounds = None
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def refresh(self):
        value = STORE.current()
        task = value.get('task') if value else None
        usable = bool(task and task.enabled and not task.paused and not task.executor.paused
                      and not task.executor.exit_event.is_set())
        bounds = game_bounds(value['hwnd']) if usable else None
        # Never position old advice onto a newly resized or unrelated window.
        if not bounds or not value['advice'] or bounds[2:] != value['size']:
            self.payload = None
            self.hide()
            return
        self.payload = value
        ratio = self.devicePixelRatioF()
        logical_size = (round(bounds[2]/ratio), round(bounds[3]/ratio))
        if (bounds != self._bounds or not self.isVisible()
                or (self.width(), self.height()) != logical_size):
            import win32con
            import win32gui
            # Physical Win32 client bounds avoid mixing Qt logical pixels with
            # Windows screen pixels at 125/150% DPI and on secondary monitors.
            import pywintypes
            try:
                # SetWindowPos alone leaves QWidget's initial 640x480 geometry
                # cached before first show. Size in Qt units, show, then place
                # the native window; otherwise show() can restore the old size.
                self.resize(*logical_size)
                self.show()
                win32gui.SetWindowPos(int(self.winId()), win32con.HWND_TOPMOST,
                                     *bounds, win32con.SWP_NOACTIVATE)
                # Crossing monitors can synchronously change the window's DPR.
                ratio = self.devicePixelRatioF()
                self.resize(round(bounds[2]/ratio), round(bounds[3]/ratio))
            except pywintypes.error:
                self.hide()
                return
            self._bounds = bounds
        self.update()

    def paintEvent(self, event):
        if self.payload:
            painter = QPainter(self)
            # Keep card layout/font/wrapping in game pixels. Qt then applies
            # its DPR once, including at 125/150% or custom framework scaling.
            try:
                ratio = self.devicePixelRatioF()
                painter.scale(1/ratio, 1/ratio)
                paint_advice(painter, self.payload['advice'], *self.payload['size'],
                             self.payload['opacity'], self.payload['language'])
            finally:
                painter.end()
