"""Validated, self-contained per-schedule settings; no shared config writes."""
import base64
import json
import re
import sys

from .policy import FARM, TIMED, NeedsReview
from .events import ONSLAUGHT

CUSTOM_TASK = "starsavior.tasks.CustomDailyTask"
MARKER = "OKSS_CUSTOM_V1:"
FLAG = "--okss-profile"
CHOICES = {"體力刷關": ["不消耗體力", *FARM],
           "限時據點關卡": ["略過", *TIMED],
           "激戰委託關卡": ["略過", *ONSLAUGHT]}


def default_profile():
    return {"執行項目": [], **{key: choices[0] for key, choices in CHOICES.items()}}


def validate_profile(value):
    from .tasks import STEPS, migrate_event_selection
    if not isinstance(value, dict):
        raise NeedsReview("自訂排程設定不完整，請修改此排程並重新儲存")
    # V1 snapshots already stored in Windows include the old event name.
    # Ignore that retired field without changing the schedule's selected tasks.
    value = {key: item for key, item in value.items() if key != "活動名稱"}
    if set(value) != set(default_profile()):
        raise NeedsReview("自訂排程設定不完整，請修改此排程並重新儲存")
    selected = value["執行項目"]
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        raise NeedsReview("自訂排程項目格式錯誤")
    selected = migrate_event_selection(selected)
    if not selected or set(selected) - {name for name, _ in STEPS}:
        raise NeedsReview("自訂排程至少需要勾選一個有效項目")
    for key, choices in CHOICES.items():
        if value[key] not in choices:
            raise NeedsReview(f"自訂排程選項不支援：{key}")
    return {**value, "執行項目": selected}


def encode_profile(profile):
    value = validate_profile(profile)
    return base64.urlsafe_b64encode(json.dumps(value, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).decode("ascii")


def decode_profile(token):
    try:
        if len(token) > 16000 or not re.fullmatch(r"[A-Za-z0-9_=-]+", token):
            raise ValueError("invalid token")
        value = json.loads(base64.b64decode(token, altchars=b"-_", validate=True))
    except (ValueError, TypeError, UnicodeError) as error:
        raise NeedsReview("自訂排程設定損毀，未改用首頁日課") from error
    return validate_profile(value)


def description_for(profile):
    return MARKER + encode_profile(profile)


def token_from_description(description):
    matches = re.findall(r"OKSS_CUSTOM_V1:([A-Za-z0-9_=-]+)", description or "")
    if len(matches) != 1:
        raise NeedsReview("找不到此排程的獨立設定，請修改排程後重新儲存")
    decode_profile(matches[0])
    return matches[0]


def profile_from_argv(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args.count(FLAG) != 1:
        raise NeedsReview("自訂任務必須從已儲存的自訂排程啟動，未使用首頁日課設定")
    index = args.index(FLAG)
    if index + 1 >= len(args):
        raise NeedsReview("自訂排程缺少執行設定")
    return decode_profile(args[index + 1])
