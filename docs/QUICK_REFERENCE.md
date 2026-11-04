# Quick Reference — God-Tier Pokerbots Competitor

## 🎯 Entry Points

| Task | Command |
|------|---------|
| Run bot (stdin/stdout) | `python3 bot.py` |
| Build release | `python3 tools/discard/build.py` |
| Run tests | `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/discard -v` |
| Local match (400h) | `python3 tools/discard/local_runner.py --hands 400 --opponent CallingStation --wire --sandbox` |
| Local match (1000h) | `python3 tools/discard/local_runner.py --hands 1000 --opponent Selective --wire --sandbox` |

---

## 📦 Module APIs

### `bot.py` — Protocol Handler
```python
handle_message(msg: dict) -> dict|None
    msg['type'] ∈ {init, new_hand, action_request, discard_request, 
                   discard_result, hand_result, notice, match_end}
    Returns JSON reply for action/discard requests only.

# Global state (persists across hands)
_timebank: TimeBank          # 60-150s cumulative
_gamestate: GameState        # Match/hand tracking + duplicate memory
_policy: BettingPolicy       # GTO + exploitation engine
```

### `policy.py` — GTO Policy Engine
```python
class BettingPolicy:
    choose_action(req: dict) -> dict
        # req: legal_actions, street, hole_cards, board, pot, 
        #      to_call, my_stack, opp_stack, raises_left
        # Returns: {'type': 'action', 'action': 'check'|'call'|'fold'|'raise', 'amount?'}
    
    choose_discard(hole_cards, board, pot, my_stack, opp_stack) -> str
        # Returns card string to discard (e.g., '7d')
    
    observe_action(street, action, bet_size, pot, to_call, board)
    observe_showdown(my_hole, opp_hole, board, action_seq)

# Preflop CFR
get_cfr_preflop_strategy(hole_cards, position, history) -> dict|None
    # position: 'SB'|'BB', history: list of action codes
    # Returns: {'CHECK': 0.3, 'RAISE_3X': 0.7, ...}

sample_cfr_action(cfr_strategy, legal_actions) -> str|None
```

### `eval7.py` — Vectorized Evaluator
```python
eval_batch(cards: (N,7) int64) -> (N,) int32 scores
    # Card id = rank*4 + suit (rank 0..12=2..A, suit 0..3=shdc)
    # Score: category<<20 | tiebreakers (4 bits each)

equity_vs_range(hole: [2], board: [0-5], n_draws=500, seed=0) -> float
    # Monte Carlo P(win) + 0.5*P(tie) vs uniform random 2-card hand

parse_card('As') -> int          # 48
card_str(48) -> 'As'
preflop_equity_3card(hole3: [3], n_draws=2000) -> float
```

### `discard.py` — Discard Strategy
```python
choose_discard(hole_cards: [3 str], board: [3 str], pot, my_stack, opp_stack, n_draws=400) -> str
    # Full Monte Carlo + blocker analysis

choose_discard_fast(hole_cards: [3 str], board: [3 str]) -> str
    # Heuristic: best 5-card hand with board (pairs > flush draw > straight draw)
```

### `board_texture.py` — Board Analysis
```python
analyze_board_texture(board_cards: [int]) -> dict
    # Returns: wet, dry, flush_draw, straight_draw, paired, trips, 
    #          broadway, connected, texture_score (0-1)

get_board_category(board_cards) -> str
    # 'dry' | 'semi_wet' | 'wet' | 'trips' | 'straight_flush'

estimate_opponent_range(board_cards, history, street) -> float
    # Equity adjustment factor for opponent's likely range

river_bluff_candidates(hole_cards, board_cards) -> [(discard, score)]
    # Blocker scores for river bluffing
```

### `hand3.py` — 3-Card Hand Classification
```python
hand_type_3card(hole: [3 int]) -> (type, strength, details)
    # Types: trips, pair, flush_draw, straight_draw_{open,1gap,2gap}, 
    #        two_suited, high_card

get_hand_type_bucket(hole: [3 int]) -> str
    # 12 strategic buckets for CFR lookup:
    # trips, pair_premium, pair_high, pair_mid,
    # flush_draw_broadway, flush_draw_other,
    # straight_draw_open_ended, straight_draw_one_gap, straight_draw_two_gap,
    # two_suited_broadway, two_suited_other,
    # high_card_broadway, high_card_other

best_discard_for_type(hole) -> {discard_idx: {kept_type, kept_strength, ...}}
preflop_equity_cluster(hole, n_draws=1000) -> (best_eq, all_eq, best_idx)
```

### `tournament.py` — Tournament Awareness
```python
class TournamentContext:
    update_hand(net, hand_id)
    get_match_state() -> 'winning_big'|'winning'|'tied'|'losing'|'losing_big'
    should_reduce_variance() -> bool
    should_increase_variance() -> bool
    get_variance_multiplier() -> float    # 0.6 | 1.0 | 1.4
    get_bluff_frequency_adj() -> float    # 0.5 | 1.0 | 1.5
    get_call_threshold_adj() -> float     # 1.1 | 1.0 | 0.9

class MatchPhaseDetector:
    get_phase(hand_id) -> 'early'|'middle'|'late'|'endgame'
    get_phase_adjustments(hand_id) -> {tightness, bluff_freq, value_bet_thresh, call_thresh}
```

### `range_vs_range.py` — Range-vs-Range Equity
```python
class RangeVSEquity:
    equity(hero_range, villain_range, board, n_draws=500) -> float
        # Ranges: [(hand_tuple, weight), ...]  hand = 2 or 3 cards
    
    get_stats() -> {cache_hits, cache_misses, hit_rate, cache_size}

class RangeBuilder:
    build_preflop_range(position, action_sequence, board=None, tendencies=None)
        # Returns: [(hand, weight), ...] all 22,100 3-card hands
    
    update_range_postflop(preflop_range, action, street, bet_size, pot, board)
        # Bayesian update
```

### `river_cfr.py` — River Mini-CFR
```python
class RiverCFR:
    solve(our_range, opp_range, board, pot, eff_stack, iterations=1000)
        # Returns: {hand_key: {'check': p, 'bet_0.5': p, 'bet_0.75': p, ...}}

class RiverExploiter:
    get_river_strategy(our_range, opp_range, board, pot, eff_stack) -> dict
    decide_river_action(my_hand, our_range, opp_range, board, pot, eff_stack, 
                        legal_actions, facing_bet=False, bet_size=0)
        # Returns: 'check' | 'fold' | 'call' | {'action': 'raise', 'size_frac', 'target'}
```

### `turn_cfr.py` — Turn Mini-CFR
```python
class TurnCFR:
    solve(our_range, opp_range, board, pot, eff_stack, to_call=0, iterations=500)
        # Returns: {hand_key: {'check': p, 'bet_0.5': p, 'raise_1.0': p, 'call': p, 'fold': p}}

class TurnExploiter:
    get_turn_strategy(our_range, opp_range, board, pot, eff_stack, to_call=0)
    decide_turn_action(my_hand, our_range, opp_range, board, pot, eff_stack, 
                       legal_actions, to_call=0)
```

### `duplicate_exploit.py` — Duplicate Deal Exploitation
```python
class DuplicateDealMemory:
    start_hand(deal_seed, hand_id, seat, my_hole, board)
    record_preflop_action(action, bet_size, position)
    record_discard(my_discard, opp_discard)
    record_postflop_action(street, action, bet_size, position)
    record_showdown(my_hole, opp_hole, board, winner, net)
    record_result(net, result_type)
    get_exploit_info() -> {opp_hole, opp_preflop_action, opp_discard, opp_postflop, board}
    known_opp_hole() -> [int]|None
    opp_tendencies_this_deal() -> dict

class DuplicateExploiter:
    get_exploit_strategy(my_hole, board, legal_actions, pot, to_call, 
                         my_stack, opp_stack, position, street)
        # Returns: {equity, known_opp_hole, perfect_info, action, size}|None
```

---

## 🃏 Card Encoding

```
Rank:  2  3  4  5  6  7  8  9  T  J  Q  K  A
       0  1  2  3  4  5  6  7  8  9  10 11 12

Suit:  s  h  d  c   (spades, hearts, diamonds, clubs)
       0  1  2  3

Card ID = rank * 4 + suit
Examples: As=48, Kh=47, 7d=26, 2c=3
```

---

## 🎲 Hand Categories (eval7 Score)

| Category | Value | Description |
|----------|-------|-------------|
| Straight Flush | 8 | 5 suited connected |
| Quads | 7 | Four of a kind |
| Full House | 6 | Trips + pair |
| Flush | 5 | 5 suited |
| Straight | 4 | 5 connected |
| Trips | 3 | Three of a kind |
| Two Pair | 2 | Two pairs |
| Pair | 1 | One pair |
| High Card | 0 | Nothing |

Score = `(category << 20) | tiebreakers` (4 bits each, descending)

---

## ⏱️ Time Budget Rules

```python
TimeBank(total_ms=60000|150000, per_response_ms=5000)
    get_budget(is_critical) -> float seconds
        # Critical: river, pot>100, to_call>30% stack, stack<50
        #   → min(4.5s, available)
        # Normal: min(0.5s, available)
    
    is_critical(req) -> bool
    start_hand() / end_hand()
```

---

## 🏁 Tournament Phases

| Stage | Hands | Cap | Key Adjustments |
|-------|-------|-----|-----------------|
| Stage 1 (Swiss) | 400 | ±400 | 6 rounds, match points (W=1, D=0.5, L=0) |
| Stage 2 (Finals) | 1000 | ±1000 | Round-robin, scores reset |

| Phase | Hands | Tightness | Bluff Freq | Value Thresh | Call Thresh |
|-------|-------|-----------|------------|--------------|-------------|
| Early | 0-25% | 1.10 | 0.80 | 1.05 | 1.05 |
| Middle | 25-50% | 1.00 | 1.00 | 1.00 | 1.00 |
| Late | 50-75% | 0.90 | 1.20 | 0.95 | 0.95 |
| Endgame | 75-100% | 0.85 | 1.30 | 0.90 | 0.90 |

---

## 🎭 Opponent Archetypes

| Type | VPIP | PFR | Agg | Counter |
|------|------|-----|-----|---------|
| NIT | 0.15 | 0.08 | 0.15 | Steal, fold to agg |
| TAG | 0.22 | 0.18 | 0.35 | Standard GTO |
| LAG | 0.35 | 0.28 | 0.55 | Trap, call light |
| FISH | 0.45 | 0.10 | 0.25 | Value bet, no bluff |
| MANIAC | 0.55 | 0.40 | 0.75 | Call down |
| STATION | 0.50 | 0.05 | 0.10 | Max value, no bluff |
| UNKNOWN | 0.30 | 0.15 | 0.30 | Default GTO |

---

## 📏 Bet Sizing Reference

```python
geometric_sizing(pot, eff_stack, streets_left=2)
    # pot * (1+r)^streets = eff_stack
    # r = (eff_stack/pot)^(1/streets) - 1

Raise Amount Logic:
    1. Base = geometric fraction × (pot + to_call)
    2. Adjust by equity: 0.8→1.3× for value, 0.7→1.2× for bluff
    3. Adjust by board: wet ×1.15, dry ×0.85
    4. Clamp to [min_raise, max_raise]
    5. Round to nearest 2 chips (big blind)
```

---

## 🔄 Duplicate Deal Flow

```
HAND N (Instance 1)                    HAND N+1 (Instance 2)
┌─────────────────────┐                ┌─────────────────────┐
│ Play GTO            │                │ Load exploit_info   │
│ Record:             │    ───SAVE──▶  │ known_opp_hole = ✓  │
│ - preflop action    │   (JSON file)  │ opp_tendencies = ✓  │
│ - discard choice    │                │                     │
│ - postflop lines    │                │ PERFECT DECISIONS:  │
│ - SHOWDOWN →        │                │ - Exact equity      │
│   opp's 2 cards!    │                │ - Optimal bet size  │
└─────────────────────┘                │ - No guessing       │
                                       └─────────────────────┘
```

---

## 🚨 Common Patterns

### Preflop Action Codes (for CFR history)
```
0: CHECK    1: RAISE_3X    2: FOLD    3: CALL
4: RAISE_9X 5: RAISE_22X
```

### Legal Actions by Situation
```python
# Acting first (to_call == 0): ['check', 'raise'] (or ['fold', 'call', 'raise'] if weird)
# Facing bet (to_call > 0):  ['fold', 'call', 'raise']
```

### Street Indices
```python
STREETS = ('preflop', 'flop', 'turn', 'river')
LENGTHS = (0, 3, 4, 5)  # board cards per street
```

---

## 🧪 Debug Commands

```bash
# Test evaluator
python3 -c "from eval7 import eval_batch, parse_card; print(eval_batch([[parse_card(c) for c in 'As Ah Kd 7h 2c 9s 3d'.split()]]))"

# Test discard
python3 -c "from discard import choose_discard; print(choose_discard(['As','Ah','Kd'], ['7h','2c','9s'], 20, 200, 200))"

# Test board texture
python3 -c "from board_texture import analyze_board_texture, parse_card; b=[parse_card(c) for c in '9s 8s 7s'.split()]; print(analyze_board_texture(b))"

# Test hand3
python3 -c "from hand3 import hand_type_3card, parse_card; h=[parse_card(c) for c in 'As Ah Kd']; print(hand_type_3card(h))"

# Run specific test
python3 -m unittest tests.discard.test_bot.TestBot.test_preflop_cfr -v
```

---

## 📐 Key Formulas

| Formula | Purpose |
|---------|---------|
| `F = 3*⌊n/2⌋ + (n%2)*next_blind` | Future blind cost (n hands remaining) |
| `M = min(200, B - F - R)` | Commitment ceiling (preserve floor R) |
| `kelly = (p*b - q)/b` | Optimal bet fraction |
| `CE = EV - λ*Var` | Certainty-equivalent EV |
| `r = (stack/pot)^(1/streets) - 1` | Geometric bet fraction |

---

*Quick Reference for `releases/discard/v1/` candidate*  
*Full docs: `docs/TECHNICAL_ARCHITECTURE.md`*