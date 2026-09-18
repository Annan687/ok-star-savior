"""Pure, portable types. No capture, input injection, network, or Windows imports."""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntFlag
from typing import Optional

class Skills(IntFlag):
    NONE = 0
    Q = 1
    W = 2
    E = 4


def integer(value: int, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def validate_board(board: tuple[int, ...]) -> None:
    if not isinstance(board, tuple) or not board:
        raise ValueError("board must be a nonempty immutable tuple")
    for value in board:
        integer(value, "digit")
        if value > 9:
            raise ValueError("digits must be in 0..9; 0 means an empty cell")


def validate_skills(value: Skills) -> None:
    if not isinstance(value, Skills) or int(value) & ~7:
        raise ValueError("skills must be a Skills mask using Q/W/E only")


@dataclass(frozen=True)
class State:
    board: tuple[int, ...]
    height: int
    width: int
    remaining_ms: int
    skills: Skills
    initial_cells: int = 150

    def __post_init__(self) -> None:
        validate_board(self.board)
        integer(self.height, "height", 1)
        integer(self.width, "width", 1)
        integer(self.remaining_ms, "remaining_ms")
        integer(self.initial_cells, "initial_cells")
        validate_skills(self.skills)
        if len(self.board) != self.height * self.width:
            raise ValueError("board length differs from height * width")
        if self.occupied > self.initial_cells:
            raise ValueError("initial_cells cannot be smaller than occupied cells")

    @property
    def occupied(self) -> int:
        return sum(value != 0 for value in self.board)


@dataclass(frozen=True)
class Action:
    # WAIT is a model policy of taking no more actions, NOT a game 'end' button.
    kind: str
    rect: Optional[tuple[int, int, int, int]] = None

    def __post_init__(self) -> None:
        if self.kind not in ("MOVE", "Q", "W", "E", "WAIT"):
            raise ValueError("unknown action kind")
        if self.kind == "MOVE":
            if not isinstance(self.rect, tuple) or len(self.rect) != 4:
                raise ValueError("MOVE requires a (top,left,bottom,right) tuple")
            for value in self.rect:
                integer(value, "rectangle coordinate")
            if self.rect[0] > self.rect[2] or self.rect[1] > self.rect[3]:
                raise ValueError("rectangle corners are reversed")
        elif self.rect is not None:
            raise ValueError("only MOVE may have a rectangle")


@dataclass(frozen=True)
class TimingProfile:
    """Injected EFFECTIVE countdown ms until an action's effect completes.

    Exclude verified animation pauses. Do not label synthetic values as measured.
    future_plan_ms applies to decisions AFTER the root action only. The root
    State time is conditional on when that action is issued, not when CPU search
    started. A live caller MUST refresh/re-evaluate time before issuing anything.
    """
    move_ms: int
    q_ms: int
    w_ms: int
    e_ms: int
    future_plan_ms: int = 0
    calibrated: bool = False
    version: str = "synthetic-unmeasured"

    def __post_init__(self) -> None:
        for name in ("move_ms", "q_ms", "w_ms", "e_ms", "future_plan_ms"):
            integer(getattr(self, name), name)
        if not isinstance(self.calibrated, bool):
            raise ValueError("calibrated must be bool")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be nonempty")

    def elapsed(self, action: Action, *, root: bool) -> int:
        if action.kind == "WAIT":
            return 0
        field = {"MOVE": "move_ms", "Q": "q_ms", "W": "w_ms", "E": "e_ms"}[action.kind]
        return getattr(self, field) + (0 if root else self.future_plan_ms)
