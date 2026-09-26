"""Read titles only when choices appear; dates disambiguate different effects."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import threading
import time

import cv2
import numpy as np

from ..vision import Text, View, norm

DATE_AREA = (.09, .075, .28, .14)
EVENT_AREA = (.11, .17, .40, .27)
CHOICE_AREA = (.67, .49, .99, .79)


def key(text):
    return re.sub(r"[^\w]", "", norm(text))


def load_cards():
    data = json.loads(Path(__file__).with_name('cards.json').read_text(encoding='utf-8'))
    seen = set()
    for card in data['cards']:
        if (card['id'] in seen or not card['effects_recorded'] or len(card['events']) > 3
                or card['image'] not in [f'{n:02}.png' for n in range(1, 8)]
                or not Path(__file__).with_name('card_tables').joinpath(card['image']).is_file()):
            raise ValueError('卡片參考資料不完整')
        seen.add(card['id'])
    return data


def load_events():
    data = json.loads(Path(__file__).with_name('events.json').read_text(encoding='utf-8'))
    if data['schema'] != 2 or not data['events']:
        raise ValueError('跑馬事件資料版本不符或為空')
    ids = set()
    for event in data['events']:
        if (event['id'] in ids or not event['name'] or not 2 <= len(event['choices']) <= 4
                or (not event['periods'] and event['category'] not in ('天氣', '訓練'))
                or not event['source']['url'].startswith(data['source'] + '?tab=')):
            raise ValueError('跑馬事件資料重複或不完整')
        ids.add(event['id'])
        aliases = set()
        for choice in event['choices']:
            choices = {key(a) for a in choice['aliases']}
            if not choices or '' in choices or not choice['lines'] or not all(choice['lines']) or aliases & choices:
                raise ValueError('跑馬選項資料不完整或有歧義')
            aliases.update(choices)
    cards = load_cards()
    card_ids = {c['id'] for c in cards['cards']}
    data['cards'] = cards['cards']
    data['card_events'] = cards['event_effects']
    for event in data['card_events']:
        if (event['id'] in ids or event['card_id'] not in card_ids or not event['name']
                or not 2 <= len(event['choices']) <= 4
                or any(not c['lines'] or not c['source_lines'] for c in event['choices'])):
            raise ValueError('卡片事件資料重複或不完整')
        ids.add(event['id'])
    return data


@dataclass(frozen=True)
class ChoiceHint:
    index: int
    x: float
    y: float
    lines: tuple[str, ...]
    column: int = 0


@dataclass(frozen=True)
class Advice:
    event_id: str
    title: str
    hints: tuple[ChoiceHint, ...]
    status: str
    warning: str = ''
    column_titles: tuple[str, ...] = ()


def search_events(data, query='', category='全部'):
    terms = [key(term) for term in query.split() if key(term)]
    return [event for event in data['events']
            if (category == '全部' or event['category'] == category)
            and all(term in key(' '.join([event['name'], *event.get('name_aliases', []), *event['periods'], event['source']['sheet'],
                                         *[a for c in event['choices'] for a in c['aliases']],
                                         *[s for c in event['choices'] for s in c['source_lines']]]))
                    for term in terms)]


def title_candidates(v, data):
    headers = {key(t.text) for t in v.within(EVENT_AREA)}
    group = event_group(v)
    training = v.has('训练事件', area=EVENT_AREA, contains=False)
    return [e for e in data.get(group, [])
            if (e.get('category') == '訓練') == bool(training) and matched_names(e, headers)]


def weather_name(text):
    # OCR read the observed dash as Chinese 一. Only the known weather prefix
    # may be dropped; never use unrestricted substring/fuzzy weather matching.
    match = re.fullmatch(r'(?:(?:今日|今天|今天的)天气一?)?(晴朗|打雷|雷雨|浓雾|大雾|热带夜晚|暴雪)', key(text))
    return {'雷雨': '打雷', '大雾': '浓雾'}.get(match[1], match[1]) if match else ''


def matched_names(event, headers):
    names = [event['name'], *event.get('name_aliases', [])]
    if event.get('category') == '天氣':
        weather = {weather_name(h) for h in headers} - {''}
        return [n for n in names if weather_name(n) in weather]
    # The observed separator after this encounter prefix reads as 一. Only
    # normalize that boundary; the remaining title must still match exactly.
    headers = {re.sub(r'^突发遭遇一', '突发遭遇', h) for h in headers}
    return [n for n in names if key(n) in headers]


def event_group(v):
    journey = v.has('旅程事件', area=EVENT_AREA, contains=False)
    card = v.has('阿爾克那事件', area=EVENT_AREA, contains=False)
    training = v.has('训练事件', area=EVENT_AREA, contains=False)
    return ('card_events' if card else 'events') if sum(map(bool, (journey, card, training))) == 1 else ''


def effect_signature(event):
    # Compare corrected display effects; original source text remains provenance.
    return tuple(tuple(c['lines']) for c in event['choices'])


def needs_date(v, data):
    return len({effect_signature(e) for e in title_candidates(v, data)}) > 1


def match_event(v, data):
    group = event_group(v)
    if not group:
        return None
    headers = {key(t.text) for t in v.within(EVENT_AREA)}
    possible = title_candidates(v, data)
    if not possible:
        status = '卡片事件名稱未匹配，可能是譯名或辨識差異' if group == 'card_events' else '此事件尚未收錄或名稱尚未辨識'
        return Advice('', '跑馬小幫手', (), status)
    if any(headers & {key(n) for n in e.get('ambiguous_aliases', [])} for e in possible):
        return Advice('', '跑馬小幫手', (), '來源表有同名不同事件，暫不顯示效果')
    if group == 'card_events' and len({effect_signature(e) for e in possible}) > 1:
        labels = {c['id']: c.get('short_name', '') for c in data['cards']}
        count = getattr(v, 'option_count', len(possible[0]['choices']))
        if (len(possible) != 2 or any(e.get('unresolved') or not labels[e['card_id']]
                                     or len(e['choices']) != count for e in possible)):
            return Advice('', '', (), '同名卡片資料或畫面選項數不符，暫不顯示效果')
        hints = []
        for column, event in enumerate(possible):
            positions = getattr(v, 'option_positions', ())
            for i, hint in enumerate(fixed_hints(event)):
                x, y = positions[i] if positions else (hint.x, hint.y)
                hints.append(ChoiceHint(hint.index, x, y, hint.lines, column))
        return Advice('|'.join(e['id'] for e in possible), possible[0]['name'], tuple(hints),
                      '同名卡片並排顯示；依所帶卡片查看', '效果依新版卡片表',
                      tuple(labels[e['card_id']] for e in possible))
    dates = {key(t.text) for t in v.within(DATE_AREA)}
    dates = {d for d in dates if re.fullmatch(r'(?:[1-9]|1[0-2]|[一二三四五六七八九十]{1,3})月(?:上旬|中旬|下旬|初)', d)}
    dated = group == 'events' and needs_date(v, data)
    if dated and len(dates) != 1:
        return Advice('', '跑馬小幫手', (), '同名事件效果不同，等待日期辨識')
    if len(dates) == 1:
        filtered = [e for e in possible if not e['periods'] or dates & {key(p) for p in e['periods']}]
        if dated or filtered:
            possible = filtered
    if not possible or len({effect_signature(e) for e in possible}) != 1:
        return Advice('', '跑馬小幫手', (), '同名事件仍無法區分，暫不顯示效果')
    event = possible[0]
    if event.get('unresolved'):
        return Advice('', event['name'], (), event['unresolved'])
    if getattr(v, 'option_count', len(event['choices'])) != len(event['choices']):
        return Advice('', event['name'], (), '畫面選項數與資料不同，待補齊效果後才能顯示')
    positions = getattr(v, 'option_positions', ())
    hints = (tuple(ChoiceHint(i+1, x, y, tuple(choice['lines']))
                   for i, ((x, y), choice) in enumerate(zip(positions, event['choices'])))
             if positions else fixed_hints(event))
    name = matched_names(event, headers)[0]
    references = [r for r in event.get('name_references', []) if key(r['name']) == key(name)]
    warning = '數值依原困難表，新表有差異' if any(r['difference'] for r in references) else ''
    if group == 'card_events':
        warning = '效果依使用者提供的新版卡片表'
    title = f"{next(iter(dates))} · {name}" if dated else name
    if event.get('category') == '天氣':
        title = weather_name(name)
        if any(r['difference'] for r in event.get('name_references', [])):
            warning = '數值依原困難表，新表有差異'
    return Advice(event['id'], title, tuple(hints),
                  '已對照事件；效果依原表選項順序', warning)


def fixed_hints(event):
    # Fixed bottom-anchored reference column, scaled with the game client.
    # The 3-option placement comes from the supplied 1600x900 attack screenshot.
    count = len(event['choices'])
    return tuple(ChoiceHint(i+1, .69, .718-(count-i-1)*.067, tuple(choice['lines']))
                 for i, choice in enumerate(event['choices']))


def option_positions(frame):
    """Find aligned white choice stars without reading option text.

    Wrapped text changes row centers and spacing. Inspect a narrow vertical
    strip, retaining the observed bottom area, spacing and star shape guards.
    """
    height, width = frame.shape[:2]
    patch = frame[round(360*height/900):round(710*height/900),
                  round(1080*width/1600):round(1110*width/1600)]
    if not patch.size:
        return ()
    patch = cv2.resize(patch, (30, 350), interpolation=cv2.INTER_AREA)
    low = patch.min(axis=2)
    mask = ((low > 185) & (patch.max(axis=2).astype(np.int16)-low < 45)).astype(np.uint8)
    _, _, stats, centers = cv2.connectedComponentsWithStats(mask)
    positions = []
    stars = 0
    for (x, y, w, h, area), (cx, cy) in zip(stats[1:], centers[1:]):
        if abs(cx-16) > 4:
            continue
        if 9 <= w <= 20 and 12 <= h <= 24 and .23 <= area/(w*h) <= .55:
            shape = mask[y:y+h, x:x+w]
            edge = max(1, h//4)
            # Choice stars taper at both ends and widen at the middle. Bright
            # costume details behind the translucent choices can share the
            # same bounding box/fill ratio, but lack this shape.
            if (shape[:edge].mean() >= .4 or shape[-edge:].mean() >= .4
                    or shape[h//2-1:h//2+2].mean() <= .5):
                continue
            positions.append((1080+cx, 360+cy))
            stars += 1
        elif 12 <= w <= 18 and 18 <= h <= 24 and .55 < area/(w*h) < .8:
            # Locked options replace the star with a padlock. Require the open
            # shackle, filled body edges and dark keyhole; do not fill gaps by guess.
            lock = cv2.resize(mask[y:y+h, x:x+w], (15,21), interpolation=cv2.INTER_NEAREST)
            if (lock[3:8,5:10].mean() < .2 and lock[10:19,1:5].mean() > .85
                    and lock[10:19,11:14].mean() > .85 and lock[12:15,7:9].mean() < .3
                    and lock[18:20,4:11].mean() > .8):
                positions.append((1080+cx, 360+y+(h-1)/2))
    positions.sort(key=lambda p: p[1])
    if (not stars or not 2 <= len(positions) <= 4 or not 620 <= positions[-1][1] <= 660
            or any(not 52 <= b[1]-a[1] <= 100 for a, b in zip(positions, positions[1:]))):
        return ()
    return tuple((x/1600, y/900) for x, y in positions)


def option_count(frame):
    return len(option_positions(frame))


def recognize(frame, ocr, data=None):
    """Gate on choice graphics, then read the title and only necessary dates."""
    height, width = frame.shape[:2]
    result = View(frame, [])
    positions = option_positions(frame)
    count = len(positions)
    if not count:
        return result
    result.option_count = count
    result.option_positions = positions
    data = load_events() if data is None else data

    def read(area, scale=1, contrast=False, binary=False):
        x, y = int(area[0]*width), int(area[1]*height)
        patch = result.crop(area)
        if scale != 1:
            patch = cv2.resize(patch, None, fx=scale, fy=scale)
        if contrast or binary:
            gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
            gray = (cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)[1] if binary
                    else cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX))
            patch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        for box in ocr(frame=patch, threshold=.70):
            result.items.append(Text(box.name, (x+box.x/scale)/width, (y+box.y/scale)/height,
                                     box.width/scale/width, box.height/scale/height))
    read(EVENT_AREA)
    group = event_group(result)
    if group and not title_candidates(result, data):
        original = result.items
        # Bounded title-only retries; never fuzzy-match OCR typos or combine
        # incompatible names from different readings. No choices are OCRed.
        for scale, binary in ((2, False), (3, True)):
            result.items = []
            read(EVENT_AREA, scale=scale, contrast=not binary, binary=binary)
            if event_group(result) == group and title_candidates(result, data):
                break
        else:
            result.items = original
    if group == 'events' and needs_date(result, data):
        read(DATE_AREA)
    return result


class StableAdvice:
    def __init__(self):
        self.previous = None
        self.count = 0

    def update(self, advice):
        signature = (advice.event_id, tuple((h.index, round(h.y, 2)) for h in advice.hints)) if advice and advice.hints else None
        self.count = self.count + 1 if signature and signature == self.previous else 1
        self.previous = signature
        if not signature:
            return advice  # Clear old effects immediately on missing/unknown UI.
        return advice if self.count >= 2 else None


class AdviceStore:
    """Worker-to-GUI mailbox. Generation tokens discard late stopped frames."""
    def __init__(self):
        self.lock = threading.Lock()
        self.generation = 0
        self.value = None

    def begin(self):
        with self.lock:
            self.generation += 1
            self.value = None
            return self.generation

    def publish(self, generation, value):
        with self.lock:
            if generation == self.generation:
                self.value = value

    def end(self, generation):
        with self.lock:
            if generation == self.generation:
                self.generation += 1
                self.value = None

    def current(self, now=None):
        with self.lock:
            value = self.value
        if value and (time.monotonic() if now is None else now)-value['time'] < 2:
            return value
        return None


STORE = AdviceStore()
