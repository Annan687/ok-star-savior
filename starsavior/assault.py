"""Optional event assault progression, with one attempt per stage per run."""

from .policy import NeedsReview
from .vision import Text, norm


ASSAULT_PROGRESS_OPTION = "襲擊自動推進"
ASSAULT_SWEEP_AREA = (.74, .84, .96, .92)
ASSAULT_ENTER_AREA = (.74, .92, .96, .99)
ASSAULT_ATTEMPTS = 8


class AssaultFlows:
    @staticmethod
    def assault_stage_slot(row, layout):
        """Map an observed grid position, without parsing its Roman suffix.

        The two-column event layouts have four fixed rows. Do not enumerate
        OCR results: an unreadable earlier card must not renumber later cards.
        Unsupported or displaced positions remain unknown.
        """
        if layout not in ("grid", "pink_grid"):
            return None
        column = 0 if .10 <= row.cx < .37 else 1 if .40 < row.cx <= .70 else None
        index = round((row.cy-.39)/.11)
        if column is None or not 0 <= index < 4 or abs(row.cy-(.39+index*.11)) > .025:
            return None
        return index*2 + column + 1

    def assault_rows(self, page, stage, layout):
        """Keep named rows, supplementing unreadable grid titles by controls.

        Every unlocked grid card has a recommended-power line below its
        title. Its complete label can locate that card without interpreting
        the title or number. The original sweep-only selector is unchanged.
        """
        rows = self.event_rows(page, stage, layout)
        if layout not in ("grid", "pink_grid"):
            return rows
        occupied = {self.assault_stage_slot(row, layout) for row in rows}
        candidates = {}
        for token in page.within((.10, .36, .70, .80)):
            if not token.key.startswith(norm("建議戰鬥力")):
                continue
            row = Text(token.text, token.x, token.y-.028, token.w, token.h)
            slot = self.assault_stage_slot(row, layout)
            if slot is not None and slot not in occupied:
                candidates.setdefault(slot, []).append(row)
        # Duplicate readings in one cell are ambiguous, not two stage cards.
        rows = rows + [found[0] for found in candidates.values() if len(found) == 1]
        # Use the fixed grid slots: small OCR height changes within one row
        # must not put its left card ahead of the higher right card. Unknown
        # positions sort first so selection validation rejects them safely.
        return sorted(rows, key=lambda t: self.assault_stage_slot(t, layout) or 9,
                      reverse=True)

    def assault_stage_page(self, page, stage, layout):
        """A named stage list, not a preparation/reward/quantity overlay."""
        return (not page.has("REWARD", "VICTORY", "DEFEAT", area=(.20, .15, .98, .8), contains=False)
                and not page.has("每日任務", "特殊任務", area=(.36, .20, .59, .30), contains=False)
                and self.event_navigation_state(page) == "stage"
                and bool(self.event_rows(page, stage, layout)))

    def assault_tickets_ready(self, page, stage, layout):
        page.assault_tickets = None
        if not self.assault_stage_page(page, stage, layout):
            return False
        page.assault_tickets = self.read_event_tickets(page)
        return page.assault_tickets is not None

    def assault_selected_state(self, page, stage, layout, old_row):
        """Keep the selected position and both button states in one frame."""
        page.assault_selection = None
        if not self.assault_stage_page(page, stage, layout):
            return False
        nearby = [row for row in self.assault_rows(page, stage, layout)
                  if abs(row.cx-old_row.cx) < .06
                  and abs(row.cy-old_row.cy) < .025]
        if len(nearby) != 1 or not self.event_row_selected(page, nearby[0], layout):
            return False
        level = (self.assault_stage_slot(nearby[0], layout)
                 if layout in ("grid", "pink_grid")
                 else self.event_selected_level(page, stage, nearby[0], layout))
        sweep = page.one("掃蕩戰鬥", "掃蕩戰門", area=ASSAULT_SWEEP_AREA, required=False)
        enter = page.one("進入", area=ASSAULT_ENTER_AREA, required=False)
        if level is None or sweep is None or enter is None:
            return False
        # A missing sweep label never means an uncleared stage. The game must
        # explicitly show a disabled sweep and a usable entry button.
        state = ("sweep" if page.enabled(sweep) else
                 "advance" if page.enabled(enter) else "locked")
        page.assault_selection = (level, state)
        return True

    def next_event_stage(self, stage, layout, attempted):
        page = self.event_wait(lambda v: self.assault_stage_page(v, stage, layout),
                               f"未辨識到 {stage} 襲擊關卡列表")
        # assault_rows is ordered high to low by grid slot or column position.
        # Roman OCR must not reorder candidates or affect the early stop.
        rows = self.assault_rows(page, stage, layout)
        for old_row in rows:
            page = self.see()
            if not self.assault_stage_page(page, stage, layout):
                raise NeedsReview("襲擊關卡頁已變動，未沿用舊位置")
            nearby = [row for row in self.assault_rows(page, stage, layout)
                      if abs(row.cx-old_row.cx) < .06
                      and abs(row.cy-old_row.cy) < .025]
            if len(nearby) != 1:
                raise NeedsReview("襲擊關卡列表已變動，未沿用舊位置")
            self.click(nearby[0])
            page = self.event_wait(
                lambda v: self.assault_selected_state(v, stage, layout, old_row),
                "未確認襲擊選中位置及掃蕩／進入狀態；未挑戰",
                stability_key=lambda v: v.assault_selection)
            level, state = page.assault_selection
            # Winning without three stars may leave sweep disabled. Never
            # challenge that same level again or move backwards to another
            # incomplete stage while trying to advance. Higher candidates
            # were already checked; lower cards need no progression scan.
            if attempted and level <= max(attempted):
                return None
            if state == "sweep":
                return None
            if state == "advance":
                return level
        return None

    def event_assault(self, stage, layout):
        if not self.task.config.get(ASSAULT_PROGRESS_OPTION, False):
            return self.event_sweep(stage, layout)

        attempted = set()
        won = []

        def summary():
            return (f"已推進{len(won)}關（至第{won[-1]}關）；" if won else "")

        for _ in range(ASSAULT_ATTEMPTS):
            page = self.event_wait(
                lambda v: self.assault_tickets_ready(v, stage, layout),
                "襲擊關卡頁或免費票券數尚未穩定；未挑戰",
                stability_key=lambda v: v.assault_tickets)
            if page.assault_tickets == 0:
                return summary() + "活動免費票券已用完"

            # The verified two-column layouts end at slot VIII. After its
            # victory there is no next stage to search for. The original
            # sweep selector still handles a win without three stars.
            if layout in ("grid", "pink_grid") and won and won[-1] == 8:
                return summary() + "最後一關已通關，使用剩餘票券掃蕩；" + self.event_sweep(stage, layout)

            level = self.next_event_stage(stage, layout, attempted)
            if level is None:
                return summary() + "目前沒有可繼續推進的關卡；" + self.event_sweep(stage, layout)
            if attempted and level <= max(attempted):
                raise NeedsReview("襲擊未確認推進到後續關卡，未重複挑戰")
            attempted.add(level)
            # This is the only battle submission for this level. A timeout or
            # unknown result propagates; it never authorizes another battle or
            # a sweep. The battle flow returns only after a settled stage list.
            result = self.fight_event_stage(stage, layout, level)
            if result is False:
                return (summary() + f"第{level}關推進失敗，改回已通關關卡；"
                        + self.event_sweep(stage, layout))
            if result is not True:
                raise NeedsReview("襲擊戰鬥結果不明，未繼續推進或掃蕩")
            won.append(level)
            self.task.log_info(f"襲擊第{level}關勝利，檢查後續關卡與剩餘票券")

        # Supported activities currently have eight stages. Reaching this
        # bound must not retry a stage or start an unbounded resource loop.
        return summary() + "已達本輪推進上限；" + self.event_sweep(stage, layout)
