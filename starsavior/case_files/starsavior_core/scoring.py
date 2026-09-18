"""True-score model under the supplied rules; utility is a separate function."""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable
from .model import Skills, integer, validate_skills


@dataclass(frozen=True)
class ScoreRules:
    # No default: caller must explicitly acknowledge the uncalibrated rounding.
    rounding: str
    points_per_cell: int = 100
    points_per_unused_skill: int = 100
    points_per_second: int = 10

    def __post_init__(self) -> None:
        if self.rounding not in ("floor_seconds", "continuous"):
            raise ValueError("rounding must be floor_seconds or continuous")
        for name in ("points_per_cell", "points_per_unused_skill", "points_per_second"):
            integer(getattr(self, name), name)


@dataclass(frozen=True)
class Terminal:
    initial_cells: int
    remaining_cells: int
    skills: Skills
    remaining_ms: int
    cleared_in_time: bool

    def __post_init__(self) -> None:
        for name in ("initial_cells", "remaining_cells", "remaining_ms"):
            integer(getattr(self, name), name)
        validate_skills(self.skills)
        if not isinstance(self.cleared_in_time, bool):
            raise ValueError("cleared_in_time must be bool")
        if self.remaining_cells > self.initial_cells:
            raise ValueError("remaining_cells exceeds initial_cells")
        if self.cleared_in_time and self.remaining_cells != 0:
            raise ValueError("a nonempty board cannot be a full clear")

    @property
    def cleared_cells(self) -> int:
        return self.initial_cells - self.remaining_cells


@dataclass(frozen=True)
class ScoreBreakdown:
    cell_points: int
    skill_points: int
    time_points: Fraction

    @property
    def total(self) -> Fraction:
        return Fraction(self.cell_points + self.skill_points) + self.time_points


def score_parts(result: Terminal, rules: ScoreRules) -> ScoreBreakdown:
    unused = sum(bool(result.skills & skill) for skill in (Skills.Q, Skills.W, Skills.E))
    time_points = Fraction(0)
    if result.cleared_in_time:
        seconds = (Fraction(result.remaining_ms, 1000) if rules.rounding == "continuous"
                   else Fraction(result.remaining_ms // 1000))
        time_points = seconds * rules.points_per_second
    return ScoreBreakdown(result.cleared_cells * rules.points_per_cell,
                          unused * rules.points_per_unused_skill, time_points)


def terminal_score(result: Terminal, rules: ScoreRules) -> Fraction:
    return score_parts(result, rules).total


@dataclass(frozen=True)
class Objective:
    mode: str = "mean_score"
    threshold: Fraction | int | None = None
    record: Fraction | int | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("mean_score", "beat_threshold", "record_gain"):
            raise ValueError("unknown objective")
        if self.mode == "beat_threshold" and self.threshold is None:
            raise ValueError("beat_threshold requires threshold")
        if self.mode == "record_gain" and self.record is None:
            raise ValueError("record_gain requires record")
        for name in ("threshold", "record"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, Fraction))):
                raise ValueError(f"{name} must be int or Fraction")

    def value(self, score: Fraction | int) -> Fraction:
        score = Fraction(score)
        if self.mode == "mean_score":
            return score
        if self.mode == "beat_threshold":
            return Fraction(score > self.threshold)
        return max(Fraction(0), score - self.record)


def checked_distribution(items: Iterable[tuple[Fraction | int, Fraction | int]]) -> list[tuple[Fraction, Fraction]]:
    merged: dict[Fraction, Fraction] = {}
    for score, probability in items:
        score, probability = Fraction(score), Fraction(probability)
        if probability < 0:
            raise ValueError("negative probability")
        if probability:
            merged[score] = merged.get(score, Fraction(0)) + probability
    if sum(merged.values(), Fraction(0)) != 1:
        raise ValueError("distribution probabilities must sum exactly to one")
    return sorted(merged.items())


def best_of_n(items: Iterable[tuple[Fraction | int, Fraction | int]], n: int,
              *, record: Fraction | int | None = None) -> Fraction:
    """Exact for a SUPPLIED IID distribution. Not an inferred real-world tail."""
    integer(n, "n", 1)
    items = checked_distribution(items)
    cumulative, previous, total = Fraction(0), Fraction(0), Fraction(0)
    for score, probability in items:
        cumulative += probability
        current = cumulative ** n
        total += (current - previous) * (score if record is None else max(score, Fraction(record)))
        previous = current
    return total


def beat_in_n(items: Iterable[tuple[Fraction | int, Fraction | int]], n: int,
              threshold: Fraction | int) -> Fraction:
    integer(n, "n", 1)
    items = checked_distribution(items)
    not_above = sum((p for s, p in items if s <= threshold), Fraction(0))
    return 1 - not_above ** n
