"""Supported activity belongs to the shipped program, never a user profile.

Update its display name together with the observed navigation and reward flows
when supporting a new activity. A renamed label alone is not new-event support.
"""

CURRENT_EVENT_KIND = "golden"
CURRENT_EVENT_NAME = "甜苦交織！黃金甜點幻想曲"

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
        "name": CURRENT_EVENT_NAME,
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
}
