"""Exact combinatorial *draw-hit* probabilities, not win equity or advice.

A caller supplies an explicit set of still-unseen out cards. This module
calculates the chance that at least one appears among future community cards.
It does NOT infer whether these cards really improve a hand or beat opponents.
"""
from __future__ import annotations
from math import comb
from typing import Sequence
from .holdem import DECK, InvalidCards, parse_cards


def draw_hit_odds(hero: Sequence[str], board: Sequence[str], outs: Sequence[str]) -> dict:
    """Exact hypergeometric odds for flop (two draws) or turn (one draw).

    All card identifiers are explicit; impossible, duplicated and exposed outs
    are rejected. No assumptions about opponents, folds, betting or payouts.
    """
    hero = parse_cards(hero, allowed_counts={2})
    board = parse_cards(board, allowed_counts={3, 4})
    exposed = parse_cards(hero + board)
    outs = parse_cards(outs)
    if set(outs) & set(exposed):
        raise InvalidCards('out_already_visible')
    remaining = len(DECK) - len(exposed)
    hits = len(outs)
    if hits > remaining:
        raise InvalidCards('too_many_outs')
    draws = 5 - len(board)
    p_next = hits / remaining
    misses = remaining - hits
    p_river = 1 - (comb(misses, draws) / comb(remaining, draws) if misses >= draws else 0.0)
    return {
        'mode': 'offline_exact_draw_hit_odds',
        'uses_openai_api': False,
        'money_actions_enabled': False,
        'action': None,
        'hero_cards': list(hero),
        'board_cards': list(board),
        'outs_cards': list(outs),
        'outs_count': hits,
        'unknown_cards': remaining,
        'cards_to_come': draws,
        'hit_next_card_probability': p_next,
        'hit_by_river_probability': p_river,
        'method': 'exact_hypergeometric',
        'caveat': 'user_supplied_outs_not_verified_as_winning_cards',
    }
