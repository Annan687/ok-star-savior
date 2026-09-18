"""Admissible NUMERIC removal bounds, not geometric attainability or a score."""
from __future__ import annotations
from fractions import Fraction
from math import comb
from .model import validate_board


def counts(board: tuple[int, ...]) -> tuple[int, ...]:
    validate_board(board)
    output = [0] * 10
    for value in board:
        if value:
            output[value] += 1
    return tuple(output)


def numeric_upper_bound(board: tuple[int, ...], q_available: bool) -> int:
    if not isinstance(q_available, bool):
        raise ValueError("q_available must be bool")
    c = counts(board)
    n = sum(c)
    q = min(5, n) if q_available else 0
    u1 = 2*c[1] + 2*c[2] + c[3] + 2*c[4] + c[5] + c[7] + q
    twice_u2 = 5*c[1] + 4*c[2] + c[3] + 4*c[4] + 2*c[5] + 3*c[7] + 2*q
    upper = min(n, u1, twice_u2 // 2)
    if not q_available and sum(d*c[d] for d in range(1, 10)) % 10:
        upper = min(upper, max(0, n - 1))
    return upper


def clear_not_ruled_out(board: tuple[int, ...], q_available: bool) -> bool:
    """True only means NOT disproved. Never use False to discard nonclear points."""
    return numeric_upper_bound(board, q_available) == sum(bool(v) for v in board)


def q_now_residue_distribution(board: tuple[int, ...]) -> tuple[Fraction, ...]:
    """Exact residue distribution for UNIFORM Q NOW; not future skill timing.

    Q removes exactly min(5, occupied) distinct cells. Empty cells are never drawn.
    Tiles, not distinct digit values, are equally likely to be selected.
    """
    c = counts(board)
    digits = [d for d in range(1, 10) for _ in range(c[d])]
    k = min(5, len(digits))
    dp = [[0]*10 for _ in range(k+1)]
    dp[0][0] = 1
    for index, digit in enumerate(digits):
        for selected in range(min(k, index+1), 0, -1):
            for residue in range(10):
                dp[selected][(residue+digit) % 10] += dp[selected-1][residue]
    denominator = comb(len(digits), k)
    return tuple(Fraction(value, denominator) for value in dp[k])


def q_now_clear_modulo_probability(board: tuple[int, ...]) -> Fraction:
    """Necessary probability for a clear after Q NOW with ordinary moves/W only.

    This is NOT the true full-clear probability, and zero does NOT imply that
    using Q later is futile (ordinary moves may reduce the board below 5 cells).
    """
    return q_now_residue_distribution(board)[sum(board) % 10]


def optimistic_score_bound(state, rules) -> Fraction:
    """Admissible optimistic SCORE, for monotone objectives only.

    It intentionally allows BOTH E's extra time AND retaining all current skills,
    ignores future costs, and ignores geometry. That looseness is safe for an
    upper bound, but must NEVER be returned as a reachable predicted score.
    """
    from .model import Skills
    from .scoring import Terminal, terminal_score
    removable = numeric_upper_bound(state.board, bool(state.skills & Skills.Q))
    remaining = state.occupied - removable
    optimistic_time = state.remaining_ms + (10000 if state.skills & Skills.E else 0)
    return terminal_score(Terminal(state.initial_cells, remaining, state.skills,
                                   optimistic_time, remaining == 0), rules)
