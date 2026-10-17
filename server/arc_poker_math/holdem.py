"""Seven-card Hold'em evaluator and reproducible *illustrative* equity engine.

Equity compares a known hero hand with a uniformly random legal opponent hand.
This is NOT a GTO solver, not an estimate of a real player's range and NOT a
recommendation to gamble. The caller must not treat EV output as a wager command.
"""
from __future__ import annotations
from collections import Counter
from itertools import combinations
from random import Random
from typing import Sequence
import math
import re

RANKS='23456789TJQKA'
SUITS='cdhs'
DECK=tuple(r+s for r in RANKS for s in SUITS)
CATEGORY=('high_card','one_pair','two_pair','three_of_a_kind','straight',
          'flush','full_house','four_of_a_kind','straight_flush')
PATTERN=re.compile(r'^(?:10|[2-9TJQKA])[cdhs]$',re.I)
class InvalidCards(ValueError): pass


def parse_cards(items:Sequence[str], *, allowed_counts=None) -> tuple[str,...]:
    if not isinstance(items,(list,tuple)):
        raise InvalidCards('cards_must_be_sequence')
    if allowed_counts is not None and len(items) not in allowed_counts:
        raise InvalidCards('card_count')
    cards=[]
    for card in items:
        if not isinstance(card,str) or not PATTERN.fullmatch(card):
            raise InvalidCards('invalid_card')
        value=card.upper().replace('10','T')[0]+card[-1].lower()
        if value not in DECK:
            raise InvalidCards('invalid_card')
        cards.append(value)
    if len(cards)!=len(set(cards)):
        raise InvalidCards('duplicate_cards')
    return tuple(cards)


def _straight_high(ranks):
    options=set(ranks)
    if 14 in options: options.add(1)
    for hi in range(14,4,-1):
        if all(hi-d in options for d in range(5)):
            return hi
    return None


def rank_five(cards:Sequence[str]) -> tuple[int,...]:
    """5-card total order: category id followed by category-specific kickers."""
    cards=parse_cards(cards,allowed_counts={5})
    ranks=[RANKS.index(c[0])+2 for c in cards]
    suits=[c[1] for c in cards]
    counts=Counter(ranks)
    pairs=sorted((r for r,n in counts.items() if n==2),reverse=True)
    trips=sorted((r for r,n in counts.items() if n==3),reverse=True)
    quads=sorted((r for r,n in counts.items() if n==4),reverse=True)
    flush=len(set(suits))==1
    straight=_straight_high(ranks)
    if flush and straight:
        return (8,straight)
    if quads:
        return (7,quads[0],max(r for r in ranks if r != quads[0]))
    if trips and pairs:
        return (6,trips[0],pairs[0])
    if flush:
        return (5,*sorted(ranks,reverse=True))
    if straight:
        return (4,straight)
    if trips:
        return (3,trips[0],*sorted((r for r in ranks if r!=trips[0]),reverse=True))
    if len(pairs)==2:
        return (2,pairs[0],pairs[1],max(r for r in ranks if r not in pairs))
    if len(pairs)==1:
        return (1,pairs[0],*sorted((r for r in ranks if r!=pairs[0]),reverse=True))
    return (0,*sorted(ranks,reverse=True))


def evaluate_seven(cards:Sequence[str]) -> tuple[int,...]:
    """Best five-card rank from 5, 6 or 7 known cards."""
    cards=parse_cards(cards,allowed_counts={5,6,7})
    return max(rank_five(combo) for combo in combinations(cards,5))


def best_hand(hero:Sequence[str],board:Sequence[str]) -> dict:
    hero=parse_cards(hero,allowed_counts={2})
    board=parse_cards(board,allowed_counts={3,4,5})
    parse_cards(hero+board)
    value=evaluate_seven(hero+board)
    return {'category':CATEGORY[value[0]],'rank_key':list(value),
            'hero':list(hero),'board':list(board)}


def equity_vs_random(hero:Sequence[str], board:Sequence[str]=(), *,
                     samples:int=1500, seed:int=0) -> dict:
    """Illustrative heads-up win/tie equity vs a uniform random two-card hand.

    On the river enumerate every opponent hand exactly (990 alternatives).
    Earlier streets Monte Carlo sample complete boards and opponent hole cards.
    Zero cards on board permitted; unknown flop chunks are NOT reconstructed.
    """
    hero=parse_cards(hero,allowed_counts={2})
    board=parse_cards(board,allowed_counts={0,3,4,5})
    used=parse_cards(hero+board)
    if type(samples) is not int or not 1 <= samples <= 100000:
        raise ValueError('invalid_samples')
    if type(seed) is not int or not 0 <= seed <= 2**63-1:
        raise ValueError('invalid_seed')
    deck=tuple(card for card in DECK if card not in used)
    win=tie=loss=0
    if len(board)==5:
        states=( (opp, board) for opp in combinations(deck,2) )
        method='exact_river'
    else:
        rng=Random(seed)
        missing=5-len(board)
        states=((tuple(draw[:2]), board+tuple(draw[2:]))
                for draw in (rng.sample(deck,2+missing) for _ in range(samples)))
        method='monte_carlo_uniform_opponent'
    for villain, final_board in states:
        mine=evaluate_seven(hero+final_board)
        theirs=evaluate_seven(villain+final_board)
        if mine>theirs:win+=1
        elif mine==theirs:tie+=1
        else:loss+=1
    total=win+tie+loss
    equity=(win+tie/2)/total
    return {'equity':equity,'win_probability':win/total,
            'tie_probability':tie/total,'loss_probability':loss/total,
            'samples':total,'method':method,
            'assumption':'uniform_random_opponent_not_real_player_range',
            'hero':list(hero),'board':list(board), 'action':None}


def _amount(value, label, *, allow_zero=True):
    if type(value) not in (int,float) or not math.isfinite(value) or (value<0 if allow_zero else value<=0):
        raise ValueError(label)


def pot_odds(pot:float, call:float) -> float:
    """Required equity to call: call / (pot_before_call + call)."""
    _amount(pot,'pot');_amount(call,'call')
    if call==0: return 0.0
    return call/(pot+call)


def estimate_pot_ev(pot:float, call:float, equity:float) -> dict:
    """Simplified showdown EV, excluding rake, future betting and range effects.

    Caller should not apply this to an unfinished hand as an action recommendation.
    """
    _amount(pot,'pot');_amount(call,'call');_amount(equity,'equity')
    if equity>1: raise ValueError('invalid_equity')
    return {'ev_chips':round(equity*pot-(1-equity)*call,6),
            'pot_odds':pot_odds(pot,call),
            'assumptions':['no_future_betting','no_rake','known_equity','not_a_betting_recommendation'],
            'action':None}
