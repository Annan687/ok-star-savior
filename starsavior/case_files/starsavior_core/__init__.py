"""Experimental offline reference core. Never controls a game or replaces a solver."""
from .model import State, Action, Skills, TimingProfile
from .scoring import ScoreRules, Terminal, Objective, terminal_score, score_parts, best_of_n, beat_in_n
from .bounds import numeric_upper_bound, clear_not_ruled_out, q_now_clear_modulo_probability
