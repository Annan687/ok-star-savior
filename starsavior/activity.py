"""Supported activity belongs to the shipped program, never a user profile.

Update its display name together with the observed navigation and reward flows
when supporting a new activity. A renamed label alone is not new-event support.
"""

CURRENT_EVENT_KIND = "serve"
CURRENT_EVENT_NAME = "戰士之心！奉獻之心！"

# Per-event evidence and layout; submission/claim logic stays shared.
ACTIVITIES = {
    "serve": {
        "name": CURRENT_EVENT_NAME,
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
}
