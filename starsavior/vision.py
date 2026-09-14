"""OCR geometry and conservative visual checks in captured client coordinates."""
import re
from dataclasses import dataclass

import cv2
import numpy as np
from opencc import OpenCC

from .policy import compact, fraction, NeedsReview

_cc = OpenCC("t2s")


def norm(text):
    return compact(_cc.convert(str(text))).replace("廻", "回")


@dataclass(frozen=True)
class Text:
    text: str
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    @property
    def key(self):
        return norm(self.text)


FULL = (0, 0, 1, 1)
TOP = (0, 0, 1, .16)
BOTTOM = (0, .67, 1, 1)
CENTER = (.20, .18, .83, .91)
RIGHT = (.67, .18, 1, 1)
LEFT = (0, .12, .30, .97)


class View:
    def __init__(self, frame, boxes):
        self.frame = frame
        h, w = frame.shape[:2]
        self.items = [Text(b.name, b.x/w, b.y/h, b.width/w, b.height/h) for b in boxes]

    def repair_icon_counts(self, recognize):
        """Re-read an impossible ticket count after isolating its colored icon.

        Never rewrite digits using a text substitution. A new OCR reading of
        the remaining pixels must preserve the denominator and be plausible.
        """
        height, width = self.frame.shape[:2]
        for token in list(self.within(TOP)):
            value = fraction(token.text)
            if not value or value[1] not in (1, 3, 6) or value[0] <= value[1]:
                continue
            bounds = self.counter_without_icon(token)
            if bounds is None:
                continue
            patch = self.crop(bounds)
            readings = recognize(patch)
            scale = 1
            if not readings:
                scale = 2
                readings = recognize(cv2.resize(patch, None, fx=scale, fy=scale))
            if len(readings) != 1:
                continue
            reading = readings[0]
            if not re.fullmatch(r"\d+\s*/\s*\d+", reading.name.strip()):
                continue
            if fraction(reading.name, value[1]) is None:
                continue
            replacement = Text(reading.name, bounds[0]+reading.x/(width*scale),
                               bounds[1]+reading.y/(height*scale),
                               reading.width/(width*scale), reading.height/(height*scale))
            self.items[self.items.index(token)] = replacement

    def counter_without_icon(self, token):
        patch = self.crop((token.x, token.y, token.x+token.w, token.y+token.h))
        if not patch.size:
            return None
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        colored = (hsv[:, :, 1] > 85) & (hsv[:, :, 2] > 75)
        columns = np.flatnonzero(colored.sum(axis=0) >= 3)
        if len(columns) < 5 or columns[0] > patch.shape[1]*.2:
            return None
        end = int(columns[-1])+2
        if not .12*patch.shape[1] < end < .6*patch.shape[1]:
            return None
        height, width = self.frame.shape[:2]
        return (token.x+end/width, max(0, token.y-3/height),
                min(1, token.x+token.w+3/width), min(1, token.y+token.h+3/height))

    def within(self, area=FULL):
        x, y, r, b = area
        return [t for t in self.items if x <= t.cx <= r and y <= t.cy <= b]

    def find(self, *labels, area=FULL, contains=False):
        keys = [norm(s) for s in labels]
        return [t for t in self.within(area)
                if any(k in t.key if contains else k == t.key for k in keys)]

    def one(self, *labels, area=FULL, contains=False, required=True):
        hits = self.find(*labels, area=area, contains=contains)
        if len(hits) == 1:
            return hits[0]
        if required:
            raise NeedsReview(f"無法唯一定位 {labels}：{[t.text for t in hits]}")
        return None

    def has(self, *labels, area=FULL, contains=True):
        return bool(self.find(*labels, area=area, contains=contains))

    def crop(self, area):
        h, w = self.frame.shape[:2]
        x, y, r, b = area
        return self.frame[max(0, int(y*h)):min(h, int(b*h)), max(0, int(x*w)):min(w, int(r*w))]

    def around(self, t, dx=.10, dy=.065):
        return max(0, t.cx-dx), max(0, t.cy-dy), min(1, t.cx+dx), min(1, t.cy+dy)

    def enabled(self, t):
        # Sample the button around its text. Only strongly colored or near-white
        # backgrounds qualify; ambiguous gray buttons are left alone.
        patch = self.crop(self.around(t, max(.032, t.w/2+.012), max(.013, t.h*.9)))
        if not patch.size:
            return False
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        bright_color = (hsv[:, :, 1] > 115) & (hsv[:, :, 2] > 160)
        white = (hsv[:, :, 1] < 35) & (hsv[:, :, 2] > 215)
        return float(bright_color.mean()) > .24 or float(white.mean()) > .50

    def max_is_gray(self, token):
        """Positive gray-background check; active MAX is black, not colored."""
        if token.key != "MAX":
            return False
        patch = self.crop((token.cx-.013, token.cy-.018,
                           token.cx+.013, token.cy+.018))
        if not patch.size:
            return False
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        gray = (hsv[:, :, 1] < 40) & (hsv[:, :, 2] >= 85) & (hsv[:, :, 2] <= 175)
        return float(gray.mean()) > .45

    def count(self, maximum=None, area=TOP, required=True, allow_overflow=False):
        hits = [(t, fraction(t.text)) for t in self.within(area)]
        hits = [(t, f) for t, f in hits if f is not None
                and (maximum is None or f[1] == maximum)
                and (allow_overflow or f[0] <= f[1])]
        if len(hits) == 1:
            return hits[0]
        if required:
            raise NeedsReview(f"剩餘次數辨識不明確：{[(t.text, f) for t,f in hits]}")
        return None

    def field(self, label, area=CENTER):
        anchor = self.one(label, area=area, contains=True)
        label_key = norm(label)
        if anchor.key.startswith(label_key) and anchor.key != label_key:
            suffix = anchor.key[len(label_key):].lstrip(":：")
            split = len(label_key)/len(anchor.key)
            return Text(suffix, anchor.x+anchor.w*split, anchor.y,
                        anchor.w*(1-split), anchor.h)
        # Only the value on the label's row, excluding descriptions above it.
        hits = [t for t in self.within(area) if t.x > anchor.x + anchor.w*.85
                and abs(t.cy-anchor.cy) < max(.020, anchor.h) and t.key != "*"]
        if len(hits) != 1:
            raise NeedsReview(f"{label} 欄位不清楚：{[t.text for t in hits]}")
        return hits[0]

    def selected_stage_row(self, row):
        """Blue left border of the selected central stage card, not star color."""
        patch = self.crop((.277, row.cy-.02, .291, row.cy+.045))
        if not patch.size:
            return False
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        blue = cv2.inRange(hsv, (85, 100, 170), (120, 255, 255))
        red = ((hsv[:, :, 0] < 9) | (hsv[:, :, 0] > 171)) & (hsv[:, :, 1] > 150) & (hsv[:, :, 2] > 170)
        return float((blue > 0).mean()) > .06 or float(red.mean()) > .06

    def available_stage_row(self, row):
        """Locked stage cards are darkened; sample the blank part of the card."""
        patch = self.crop((.47, row.cy-.01, .62, row.cy+.02))
        return bool(patch.size and float(np.median(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 2])) > 135)

    def same_currency(self, top_count, cost):
        """Compare the icon immediately left of count and cost in this frame.

        No assumption that every ticket-like icon is the same currency.
        Missing/misread numbers or different icon geometry fail closed.
        """
        source = self.crop((top_count.x-.024, top_count.cy-.016,
                            top_count.x-.003, top_count.cy+.016))
        target = self.crop((cost.x-.050, cost.cy-.032, cost.x+.004, cost.cy+.032))
        if not source.size or not target.size or source.std() < 18:
            return False
        best = -1
        for scale in (.75, .9, 1.0, 1.15, 1.3):
            resized = cv2.resize(source, None, fx=scale, fy=scale)
            if resized.shape[0] <= target.shape[0] and resized.shape[1] <= target.shape[1]:
                score = cv2.matchTemplate(target, resized, cv2.TM_CCOEFF_NORMED)
                best = max(best, float(score.max()))
        return best > .86

    def outline_targets(self, area, color="blue"):
        """Closed, thin highlighted rectangles; never select by colorful items."""
        patch = self.crop(area)
        if not patch.size:
            return []
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        if color == "blue":
            mask = cv2.inRange(hsv, (85, 90, 175), (120, 255, 255))
        else:
            mask = cv2.inRange(hsv, (10, 70, 185), (40, 255, 255))
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        height, width = self.frame.shape[:2]
        hits = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if not (.035*width < w < .17*width and .04*height < h < .30*height):
                continue
            if color == "yellow" and not (.75 < w/h < 1.33 and h < .16*height):
                continue
            band = 5 if color == "yellow" else 3
            edges = [mask[y:y+band, x:x+w], mask[y+h-band:y+h, x:x+w],
                     mask[y:y+h, x:x+band], mask[y:y+h, x+w-band:x+w]]
            coverage = [float((e > 0).mean()) for e in edges]
            if min(coverage) < (.25 if color == "yellow" else .40) or np.mean(coverage) < .40:
                continue
            inner = mask[y+5:y+h-5, x+5:x+w-5]
            if not inner.size or float((inner > 0).mean()) > .35:
                continue
            token = Text("highlight", area[0]+x/width, area[1]+y/height, w/width, h/height)
            if not any(abs(token.cx-t.cx) < .02 and abs(token.cy-t.cy) < .02 for t in hits):
                hits.append(token)
        return hits

    def close_icon(self, area):
        """Locate a small light or dark X inside the expected dialog corner."""
        patch = self.crop(area)
        h, w = self.frame.shape[:2]
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        candidates = []
        for mask in (cv2.inRange(gray, 200, 255), cv2.inRange(gray, 0, 70)):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, cw, ch = cv2.boundingRect(contour)
                if not (.007*w < cw < .026*w and .007*w < ch < .026*w and .75 < cw/ch < 1.33):
                    continue
                small = cv2.resize(mask[y:y+ch, x:x+cw], (21, 21)) > 0
                yy, xx = np.indices((21, 21))
                cross = (abs(xx-yy) <= 3) | (abs(xx+yy-20) <= 3)
                if small[cross].mean() > .65 and small[~cross].mean() < .18:
                    candidates.append(Text("X", area[0]+x/w, area[1]+y/h, cw/w, ch/h))
        if len(candidates) != 1:
            raise NeedsReview(f"關閉叉叉辨識不明確：{len(candidates)} 個候選")
        return candidates[0]

    def number_near_button(self, button):
        hits = [t for t in self.within((button.cx, button.cy-.03, min(1, button.cx+.15), button.cy+.035))
                if re.fullmatch(r"[\d,]+", compact(t.text))]
        if len(hits) != 1:
            raise NeedsReview("未能辨識按鈕右側的消耗數量")
        return hits[0], int(compact(hits[0].text).replace(",", ""))

    def menu_icon(self):
        area = (.925, .015, .98, .095)
        patch = self.crop(area)
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 0, 215), (180, 45, 255))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = self.frame.shape[:2]
        squares = []
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            if .004*w < cw < .012*w and .7 < cw/max(ch, 1) < 1.4:
                squares.append((x+cw/2, y+ch/2))
        if len(squares) != 4:
            return None
        xs, ys = zip(*squares)
        if max(xs)-min(xs) > .02*w or max(ys)-min(ys) > .02*w:
            return None
        return Text("四格選單", area[0]+sum(xs)/4/w-.005,
                    area[1]+sum(ys)/4/h-.005, .01, .01)
