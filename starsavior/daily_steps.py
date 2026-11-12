"""Ordered daily tasks shared by the GUI and schedules."""

STEPS = [
    ("登入彈窗", "startup"), ("支援金與免費緊急支援", "support"), ("郵件", "mail"),
    ("好友點數", "friends"), ("付費商店免費禮包", "paid_shop"), ("啟示錄商店", "apocalypse"),
    ("探索委託免費券", "exploration"), ("體力刷關", "stamina"), ("帕萊斯立方", "cube"),
    ("限時據點", "timed"), ("星際迴廊", "corridors"), ("策略戰", "strategy"),
    ("活動襲擊", "event"), ("活動任務", "event_missions"), ("環形鏈路", "activity_orbital"),
    ("激戰委託", "onslaught"),
    ("每日與每週任務", "missions"),
    ("地區派遣", "dispatch"), ("公會", "guild"), ("通行證", "passes"),
]


def migrate_event_selection(selected):
    """Expand the former combined task in saved settings and schedules."""
    result = []
    for name in selected:
        for target in (("活動襲擊", "活動任務") if name == "活動襲擊與任務" else (name,)):
            if target not in result:
                result.append(target)
    return result
