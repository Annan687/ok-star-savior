"""Bounded exact small-board reference planner: MOVE / Q / W / E together.

NOT the full-board real-time replacement. The model assumes uniform Q, uniform
W over occupied slots, no refill, skills still usable on a no-move board, and an
action takes effect strictly BEFORE the countdown reaches zero. Timings are
injected. The actual game termination and animation boundaries need calibration.

Incomplete chance branches NEVER get averaged or reported as exact. Completed
subproblems are cached only for this solve, binding them to timing/rules/objective.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import combinations
from math import comb, factorial
from time import perf_counter
from typing import Callable, Iterator
from .model import State, Skills, Action, TimingProfile, integer
from .scoring import Terminal, ScoreRules, Objective, terminal_score
from .bounds import optimistic_score_bound


class SearchLimit(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    max_occupied: int = 10
    max_nodes: int = 50000
    wall_ms: int = 1000
    max_w_outcomes: int = 720
    max_cache_entries: int = 10000

    def __post_init__(self) -> None:
        for name in ("max_occupied", "max_nodes", "wall_ms", "max_w_outcomes", "max_cache_entries"):
            integer(getattr(self, name), name)


class Budget:
    def __init__(self, limits: Limits, clock: Callable[[], float]) -> None:
        self.limits, self.clock = limits, clock
        self.started = clock()
        self.deadline = self.started + limits.wall_ms / 1000
        self.nodes = 0

    def check(self) -> None:
        if self.clock() >= self.deadline:
            raise SearchLimit("wall_deadline")

    def node(self) -> None:
        self.check()
        if self.nodes >= self.limits.max_nodes:
            raise SearchLimit("node_limit")
        self.nodes += 1


@dataclass(frozen=True)
class Distribution:
    outcomes: tuple[tuple[Terminal, Fraction], ...]

    def __post_init__(self) -> None:
        if not self.outcomes or any(p < 0 for _, p in self.outcomes):
            raise ValueError("invalid probabilities")
        if sum((p for _, p in self.outcomes), Fraction(0)) != 1:
            raise ValueError("probabilities must sum to one")

    def expected_score(self, rules: ScoreRules) -> Fraction:
        return sum((p * terminal_score(t, rules) for t, p in self.outcomes), Fraction(0))

    def utility(self, objective: Objective, rules: ScoreRules) -> Fraction:
        return sum((p * objective.value(terminal_score(t, rules)) for t, p in self.outcomes), Fraction(0))

    @property
    def clear_probability(self) -> Fraction:
        return sum((p for t, p in self.outcomes if t.cleared_in_time), Fraction(0))

    @property
    def expected_cleared_cells(self) -> Fraction:
        return sum((p * t.cleared_cells for t, p in self.outcomes), Fraction(0))

    @property
    def expected_unused_skills(self) -> Fraction:
        return sum((p * sum(bool(t.skills & x) for x in (Skills.Q, Skills.W, Skills.E))
                    for t, p in self.outcomes), Fraction(0))

    def score_distribution(self, rules: ScoreRules) -> tuple[tuple[Fraction, Fraction], ...]:
        merged: dict[Fraction, Fraction] = {}
        for terminal, probability in self.outcomes:
            score = terminal_score(terminal, rules)
            merged[score] = merged.get(score, Fraction(0)) + probability
        return tuple(sorted(merged.items()))


def _distribution(merged: dict[Terminal, Fraction]) -> Distribution:
    return Distribution(tuple(sorted(merged.items(), key=lambda pair: (
        pair[0].initial_cells, pair[0].remaining_cells, int(pair[0].skills),
        pair[0].remaining_ms, pair[0].cleared_in_time))))


def _stop(state: State) -> Distribution:
    empty = state.occupied == 0
    # WAIT is the feasible policy 'do nothing else until the game ends'.
    terminal = Terminal(state.initial_cells, state.occupied, state.skills,
                        state.remaining_ms if empty else 0,
                        empty and state.remaining_ms > 0)
    return Distribution(((terminal, Fraction(1)),))


def _noop() -> None:
    pass


def legal_moves(state: State, check: Callable[[], None] = _noop) -> Iterator[Action]:
    """All distinct occupied-cell sets selected by sum-10 rectangles.

    Only occupied coordinates are needed for canonical boundaries. This is NOT
    arbitrary subset selection; every occupied cell inside the rectangle counts.
    """
    occupied = [(i, i // state.width, i % state.width, value)
                for i, value in enumerate(state.board) if value]
    rows = sorted({r for _, r, _, _ in occupied})
    cols = sorted({c for _, _, c, _ in occupied})
    seen: set[tuple[int, ...]] = set()
    for ai, top in enumerate(rows):
        for bottom in rows[ai:]:
            for bi, left in enumerate(cols):
                for right in cols[bi:]:
                    check()
                    selected = [(i, r, c, value) for i, r, c, value in occupied
                                if top <= r <= bottom and left <= c <= right]
                    if sum(value for _, _, _, value in selected) != 10:
                        continue
                    ids = tuple(i for i, _, _, _ in selected)
                    if ids in seen:
                        continue
                    seen.add(ids)
                    yield Action("MOVE", (min(r for _, r, _, _ in selected),
                                          min(c for _, _, c, _ in selected),
                                          max(r for _, r, _, _ in selected),
                                          max(c for _, _, c, _ in selected)))


def _selected(state: State, action: Action) -> tuple[int, ...]:
    if action.kind != "MOVE" or action.rect is None:
        raise ValueError("not a rectangle move")
    top, left, bottom, right = action.rect
    if bottom >= state.height or right >= state.width:
        raise ValueError("rectangle out of bounds")
    ids = tuple(r*state.width+c for r in range(top, bottom+1)
                for c in range(left, right+1) if state.board[r*state.width+c])
    if sum(state.board[i] for i in ids) != 10:
        raise ValueError("illegal rectangle: sum must be 10")
    return ids


def unique_permutations(values: tuple[int, ...], check: Callable[[], None]) -> Iterator[tuple[int, ...]]:
    counts = Counter(values)
    keys = sorted(counts)
    prefix: list[int] = []
    def visit() -> Iterator[tuple[int, ...]]:
        check()
        if len(prefix) == len(values):
            yield tuple(prefix)
            return
        for value in keys:
            check()
            if counts[value]:
                counts[value] -= 1
                prefix.append(value)
                yield from visit()
                prefix.pop()
                counts[value] += 1
    yield from visit()


@dataclass(frozen=True)
class ActionEvaluation:
    action: Action
    distribution: Distribution
    fully_evaluated: bool
    # Incomplete evaluation is the feasible action-then-WAIT policy, not a
    # partial chance average. Its utility is a policy lower bound.
    note: str = "exact under supplied model"


@dataclass(frozen=True)
class Decision:
    action: Action
    distribution: Distribution
    complete: bool
    selected_action_fully_evaluated: bool
    evaluations: tuple[ActionEvaluation, ...]
    nodes: int
    wall_ms: float
    limit_reasons: tuple[str, ...]
    cached_states: int
    pruned_states: int


class ExactPlanner:
    def __init__(self, rules: ScoreRules, objective: Objective, timing: TimingProfile,
                 limits: Limits | None = None, *, clock: Callable[[], float] = perf_counter):
        self.rules, self.objective, self.timing = rules, objective, timing
        self.limits, self.clock = limits or Limits(), clock
        self.cache: dict[State, Distribution] = {}
        self.budget: Budget | None = None
        self.pruned_states = 0

    def _rank(self, distribution: Distribution) -> tuple[Fraction, Fraction, Fraction]:
        # Only objective ties use mean true score, then expected saved skills.
        # There is no two-cell preference or arbitrary full-clear reward.
        return (distribution.utility(self.objective, self.rules),
                distribution.expected_score(self.rules), distribution.expected_unused_skills)

    def _actions(self, state: State, *, root: bool) -> Iterator[Action]:
        if not state.occupied or not state.remaining_ms:
            return
        for action in legal_moves(state, self.budget.check):
            if self.timing.elapsed(action, root=root) < state.remaining_ms:
                yield action
        for name, skill in (("Q", Skills.Q), ("W", Skills.W), ("E", Skills.E)):
            self.budget.check()
            action = Action(name)
            if state.skills & skill and self.timing.elapsed(action, root=root) < state.remaining_ms:
                yield action

    def transitions(self, state: State, action: Action, *, root: bool = True) -> Iterator[tuple[State, Fraction]]:
        """Exact chance outcomes. Public for independent tests; needs solve budget.

        W remains a valid success even when the arrangement stays unchanged.
        No real-world confirmation of a skill is implemented here.
        """
        if self.budget is None:
            raise RuntimeError("initialize planner using solve before transitions")
        self.budget.check()
        if not state.occupied or not state.remaining_ms:
            raise ValueError("terminal state has no executable action")
        cost = self.timing.elapsed(action, root=root)
        if cost >= state.remaining_ms:
            raise ValueError("action cannot finish strictly before zero")
        remaining = state.remaining_ms - cost
        if action.kind == "MOVE":
            ids = _selected(state, action)
            board = list(state.board)
            for index in ids:
                board[index] = 0
            yield replace(state, board=tuple(board), remaining_ms=remaining), Fraction(1)
            return
        if action.kind not in ("Q", "W", "E"):
            raise ValueError("WAIT has no transition; evaluate its terminal policy")
        skill = {"Q": Skills.Q, "W": Skills.W, "E": Skills.E}[action.kind]
        if not state.skills & skill:
            raise ValueError("skill is unavailable")
        skills = Skills(int(state.skills) & ~int(skill))
        if action.kind == "E":
            yield replace(state, skills=skills, remaining_ms=remaining+10000), Fraction(1)
            return
        occupied = tuple(i for i, value in enumerate(state.board) if value)
        if action.kind == "Q":
            k = min(5, len(occupied))
            probability = Fraction(1, comb(len(occupied), k))
            for ids in combinations(occupied, k):
                self.budget.check()
                board = list(state.board)
                for index in ids:
                    board[index] = 0
                yield replace(state, board=tuple(board), remaining_ms=remaining, skills=skills), probability
            return
        values = tuple(state.board[i] for i in occupied)
        number = factorial(len(values))
        for count in Counter(values).values():
            number //= factorial(count)
        if number > self.limits.max_w_outcomes:
            raise SearchLimit("w_outcome_limit")
        probability = Fraction(1, number)
        for permutation in unique_permutations(values, self.budget.check):
            board = list(state.board)
            for index, value in zip(occupied, permutation):
                board[index] = value
            yield replace(state, board=tuple(board), remaining_ms=remaining, skills=skills), probability

    def _action_value(self, state: State, action: Action, *, root: bool) -> Distribution:
        merged: dict[Terminal, Fraction] = {}
        for child, chance_probability in self.transitions(state, action, root=root):
            child_value = self._value(child)
            for terminal, policy_probability in child_value.outcomes:
                self.budget.check()
                merged[terminal] = merged.get(terminal, Fraction(0)) + chance_probability*policy_probability
        # This point is reached only when ALL chance outcomes were completed.
        return _distribution(merged)

    def _value(self, state: State) -> Distribution:
        self.budget.check()
        if state in self.cache:
            return self.cache[state]
        self.budget.node()
        best = _stop(state)
        ceiling = optimistic_score_bound(state, self.rules)
        upper_rank = (self.objective.value(ceiling), ceiling,
                      Fraction(sum(bool(state.skills & x) for x in (Skills.Q, Skills.W, Skills.E))))
        if self._rank(best) >= upper_rank:
            self.pruned_states += 1
            if len(self.cache) < self.limits.max_cache_entries:
                self.cache[state] = best
            return best
        for action in self._actions(state, root=False):
            value = self._action_value(state, action, root=False)
            if self._rank(value) > self._rank(best):
                best = value
        if len(self.cache) < self.limits.max_cache_entries:
            self.cache[state] = best  # Never cache an incomplete state as exact.
        return best

    def _action_then_wait(self, state: State, action: Action) -> Distribution:
        """An inexpensive complete fallback policy, without sampling random boards."""
        remaining = state.occupied
        skills = state.skills
        time_left = state.remaining_ms - self.timing.elapsed(action, root=True)
        if action.kind == "MOVE":
            remaining -= len(_selected(state, action))
        elif action.kind in ("Q", "W", "E"):
            skill = {"Q": Skills.Q, "W": Skills.W, "E": Skills.E}[action.kind]
            skills = Skills(int(skills) & ~int(skill))
            if action.kind == "Q":
                remaining -= min(5, remaining)
            elif action.kind == "E":
                time_left += 10000
        terminal = Terminal(state.initial_cells, remaining, skills,
                            time_left if remaining == 0 else 0, remaining == 0)
        return Distribution(((terminal, Fraction(1)),))

    def solve(self, state: State) -> Decision:
        if state.occupied > self.limits.max_occupied:
            raise ValueError("small-board oracle limit exceeded; use full-board engine, not this oracle")
        self.cache = {}
        self.pruned_states = 0
        self.budget = Budget(self.limits, self.clock)
        best = ActionEvaluation(Action("WAIT"), _stop(state), True, "no-more-actions policy")
        evaluations: list[ActionEvaluation] = [best]
        reasons: set[str] = set()
        try:
            self.budget.node()
            for action in self._actions(state, root=True):
                # A complete feasible lower-bound policy is available BEFORE a
                # potentially interrupted exact expansion.
                evaluation = ActionEvaluation(action, self._action_then_wait(state, action), False,
                                              "feasible action-then-WAIT lower bound")
                try:
                    value = self._action_value(state, action, root=True)
                    evaluation = ActionEvaluation(action, value, True)
                except SearchLimit as error:
                    reasons.add(str(error))
                evaluations.append(evaluation)
                if self._rank(evaluation.distribution) > self._rank(best.distribution):
                    best = evaluation
                elif (evaluation.action == best.action and evaluation.fully_evaluated
                      and self._rank(evaluation.distribution) == self._rank(best.distribution)):
                    best = evaluation
                self.budget.check()
        except SearchLimit as error:
            reasons.add(str(error))
        return Decision(best.action, best.distribution, not reasons,
                        best.fully_evaluated, tuple(evaluations), self.budget.nodes,
                        (self.clock()-self.budget.started)*1000,
                        tuple(sorted(reasons)), len(self.cache), self.pruned_states)
