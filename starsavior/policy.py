"""Pure decision rules. No window access or clicks in this module."""
import re
import unicodedata
from dataclasses import dataclass

FARM = {
    "乙太塵埃": ("探索委託", "城市巡邏"),
    "月光水": ("探索委託", "據點調查"),
    "負質量物質": ("探索委託", "遺跡探索"),
    "扭曲的情感": ("討伐委託", "扭曲的情感"),
    "酷寒襲擊": ("討伐委託", "酷寒襲擊"),
    "被遺忘的誓言": ("討伐委託", "被遺忘的誓言"),
}
TIMED = {
    "經理格雷戈里": ("救援者", "經理格雷戈里"),
    "卡本龐克可汗": ("救援者", "卡本龐克可汗"),
    "族長克倫納敦": ("救援者", "族長克倫納敦"),
    **{name: ("阿爾克那", name) for name in (
        "虛空涅槃者", "虛空抹殺者", "虛空屠殺者", "虛空蔑視者", "虛空流亡者", "雷塔爾吉亞的魔術師")},
    "晨星綻放石／現成歡樂68號": ("晨星綻放石", "進入"),
}


class NeedsReview(RuntimeError):
    """The current evidence is insufficient; do not issue another input."""


def compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text))).upper()


def fraction(text, maximum=None):
    """Reject ambiguous, negative or impossible OCR counts (no guessed zeros)."""
    matches = re.findall(r"(?<![\d.\-])(\d+)\s*/\s*(\d+)(?![\d.])", str(text))
    values = [(int(a), int(b)) for a, b in matches if int(b) > 0]
    if maximum is not None:
        values = [(a, b) for a, b in values if b == maximum]
    if len(values) != 1:
        return None
    a, b = values[0]
    return (a, b) if maximum is None or a <= b else None


def is_free(value):
    # Caller passes the cost field alone, NEVER a whole dialog description.
    return compact(value) in {"免費", "免费", "FREE"}


def exact_challenge(value):
    return compact(value) in {"挑戰", "挑战"}


def sweep_budget(remaining, count, cost, resource, intended):
    if None in (remaining, count, cost) or remaining < 0 or count <= 0 or cost <= 0:
        return False
    return resource == intended and cost <= remaining and (resource == "stamina" or count == cost)


def expected_open(weekday):
    """Monday=0. Informational only; the actual CLOSED/ticket UI takes priority."""
    return [name for name, days in {"太陽迴廊": {0, 3, 6}, "月亮迴廊": {1, 4, 6},
                                   "星辰迴廊": {2, 5, 6}}.items() if weekday in days]


def roman_value(text):
    value = compact(text)
    if value.isdecimal():
        return int(value)
    if not re.fullmatch(r"[IVXLCDM]+", value):
        return None
    total = last = 0
    for char in reversed(value):
        n = dict(I=1, V=5, X=10, L=50, C=100, D=500, M=1000)[char]
        total += -n if n < last else n
        last = max(last, n)
    return total


@dataclass(frozen=True)
class Result:
    step: str
    status: str
    detail: str
