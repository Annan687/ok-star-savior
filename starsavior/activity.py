"""Supported activity belongs to the shipped program, never a user profile.

Update its display name together with the observed navigation and reward flows
when supporting a new activity. A renamed label alone is not new-event support.
"""

CURRENT_EVENT_KIND = "journey_end"
CURRENT_ASSAULT_KINDS = (CURRENT_EVENT_KIND, "exile")
ONSLAUGHT = ("封閉的心象", "異形的攻勢", "虛假的契約")
ONSLAUGHT_CARD = "onslaught-list.png"
EVENT_CARD_AREA = (.35, .55, .95, .82)
GRID_LAYOUTS = ("grid", "pink_grid", "journey_grid")
POSITIONAL_COLUMNS = {
    "exile_column": (.189, .102, 5),
    "onslaught_column": (.189, .102, 6),
}

# Per-event evidence and layout; submission/claim logic stays shared.
ACTIVITIES = {
    "serve": {
        "name": "戰士之心！奉獻之心！",
        "stage": "還森林一片潔淨", "layout": "pink_grid",
        "card_logo": "serve-list.png", "home_logo": "serve-home.png",
        "home_logo_area": (.35, .56, .66, .69),
        "progress_area": (.34, .90, .42, .95),
        "links": {
            "劇情": (.18, .65, .23, .70),
            "襲擊": (.205, .745, .253, .793),
            "環形鏈路": (.223, .84, .298, .884),
            "任務": (.77, .65, .82, .70),
            "商店": (.745, .745, .794, .793),
        },
        "orbital_title": "戰士之心！奉獻之心！",
        "orbital_title_area": (.47, .83, .58, .87),
        "mission_close_light": 235,
    },
    "golden": {
        "name": "甜苦交織！黃金甜點幻想曲",
        "stage": "偽裝潛入深域", "layout": "snowfield",
        "card_logo": "golden-list.png", "home_logo": "golden-home.png",
        "home_logo_area": (.35, .64, .66, .89),
        "progress_area": (.68, .10, .75, .17),
        "links": {
            "故事": (.26, .73, .31, .78),
            "襲擊": (.18, .82, .23, .87),
            "挑戰": (.26, .89, .31, .94),
            "任務": (.77, .82, .82, .87),
            "商店": (.69, .89, .74, .94),
        },
        # User requested that this activity never run orbital, even if an
        # existing daily/schedule selection still contains that task.
        "orbital_enabled": False,
        "mission_close_light": 235,
    },
    "journey_end": {
        "name": "旅程的終點",
        "stage": "傾瀉而下的夜色", "layout": "journey_grid",
        "stage_heading": ("襲擊", (.105, .28, .175, .35)),
        "card_logo": "journey-list.png", "home_logo": "journey-home.png",
        "home_logo_area": (.08, .46, .36, .62),
        "home_labels": {"故事": (.18, .76, .26, .83)},
        # The Chinese client currently displays these buttons in Korean.
        # Positions are used only after confirming the event's own home.
        "fixed_links": {
            "襲擊": (.916, .296),
            "環形鏈路": (.891, .394),
            "任務": (.916, .493),
        },
        "read_tickets_on_stage": True,
        "orbital_title": "旅程的終點環形鏈路",
        "orbital_title_area": (.055, .135, .20, .18),
        "orbital_balance_area": (.90, .05, .943, .095),
        "mission_close_light": 235,
    },
    "exile": {
        "name": "放逐者的歸還軌跡",
        "stage": "最終評鑑戰", "layout": "exile_column",
        "stage_heading": ("關卡", (.063, .88, .13, .95)),
        "card_logo": "exile-list.png", "home_logo": "exile-home.png",
        "home_logo_area": (.05, .13, .365, .39),
        "links": {
            "故事": (.19, .51, .26, .56),
            "關卡": (.19, .64, .25, .70),
            "商店": (.19, .78, .25, .83),
        },
        "assault_link": "關卡",
        "read_tickets_on_stage": True,
        "orbital_enabled": False,
    },
}

CURRENT_EVENT_NAME = ACTIVITIES[CURRENT_EVENT_KIND]["name"]
CURRENT_ASSAULT_NAMES = "、".join(ACTIVITIES[kind]["name"] for kind in CURRENT_ASSAULT_KINDS)
