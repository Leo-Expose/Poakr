# Discard Hold'em Bot — Submission Specification

Python 3.11 bot for the Pokerbots Discard Hold'em tournament (heads-up Texas Hold'em, 3 hole cards, simultaneous exposed discard after the flop).

**Submission:** `bot.py` (single file at the root of the submission, ~66 KB, standard library + NumPy only).  
SHA-256: `155a1b52f5c264d531692298f25a6c5961b06adfd4e30ff6f4ec62284a8f9057`

---

## Core Strategy & Architecture

### 1. Bayesian Opponent Discard Inferrer (`_opp_discard_consistency`)
In Discard Hold'em, both players reveal their discarded card after the flop:
- Evaluates candidate opponent pairs against their exposed discard in a fast vectorized pass.
- Holdings where keeping the pair was consistent with maximizing flop score receive full weight; contradicted holdings are exponentially discounted.
- Turn and river equity calculations condition on this exact posterior holding distribution rather than assuming uniform random holdings.

### 2. Heads-Up Preflop Strategy
- **Button Opening:** Opens $\approx 85\%$ of hands from the Button with a 2.0x min-raise to 4 chips ($q \ge 0.44$). Folds only uncoordinated low trash.
- **Big Blind Defense:** Defends wide against min-raises ($q \ge 0.38$), and 3-bets with top holdings ($q > 0.62$).

### 3. Flop Texture & Continuation Betting
- **Dry / Paired Textures:** High-frequency small c-bet sizing ($30\%\text{--}33\%$ pot) on dry boards to exploit preflop range advantage and deny free cards.
- **Wet / Connected Textures:** Polarized sizing ($60\%$ pot) with made hands and high-equity draws; checks back marginal showdown value.

### 4. River Call Discipline & Pot-Odds
- Evaluates exact break-even pot odds price facing bets:
  $$\text{Price} = \frac{\text{To\_Call}}{\text{Pot} + \text{To\_Call}}$$
- Calls when hand equity $q \ge \text{Price} + \text{margin}$.
- In **Shield Mode** (protecting a lead $\ge +150$ chips late in the leg), applies an additional risk premium to avoid marginal coin-flip variance.

### 5. Opponent Modeling (Beta Priors)
- Tracks opponent frequencies with $\text{Beta}(\alpha, \beta)$ priors per bet-size bucket (`small`, `mid`, `big`), allowing fast adaptation from the first few hands.
- Detects hyper-aggressive shoving bots (`shove_count >= 3`) and snaps them off with $\ge 48\%$ equity.
- Dynamically classifies opponent tendencies into behavioral profiles (station, nit, shover, balanced), adjusting value sizing and steal frequencies accordingly.

### 6. Discard Selection & Camouflage
- Evaluates candidate discards by simulating post-discard equity on the flop texture, factoring in draw potential (flush/straight draws).
- Injects $25\%$ mixed-strategy entropy when the top two discard choices are within $1.5\%$ EV of each other to prevent opponent bots from deducing exact hole cards.

---

## Local Verification Commands

To run matches and check metrics using Python 3.11:

```bash
# 1. Run a 400-hand Stage 1 match against the example random bot (seed 42)
python3.11 "Starter Kit/Starter_Kit/engine.py" bot.py "Starter Kit/Starter_Kit/example_bots/random_bot.py" --stage 1 --seed 42

# 2. Run a 1000-hand Stage 2 match against the example random bot (seed 42)
python3.11 "Starter Kit/Starter_Kit/engine.py" bot.py "Starter Kit/Starter_Kit/example_bots/random_bot.py" --stage 2 --seed 42

# 3. Check memory footprint (peak RSS) under Python 3.11
python3.11 -c "
import resource, bot
b = bot.Bot()
b.handle({'type': 'init', 'total_hands': 500, 'time_bank_ms': 75000, 'per_response_ms': 5000})
for i in range(100):
    b.handle({'type': 'new_hand', 'hand_id': i+1, 'seat': 'button', 'hole_cards': ['As', 'Kd', '2c'], 'stack': 200, 'opp_stack': 200})
    b.handle({'type': 'discard_request', 'hand_id': i+1, 'hole_cards': ['As', 'Kd', '2c'], 'board': ['Ah', 'Kh', '3s'], 'pot': 20, 'my_stack': 190, 'opp_stack': 190, 'time_left_ms': 75000})
    b.handle({'type': 'discard_result', 'hand_id': i+1, 'my_discard': '2c', 'opp_discard': 'Qh', 'hole_cards': ['As', 'Kd']})
    b.handle({'type': 'action_request', 'hand_id': i+1, 'street': 'turn', 'board': ['Ah', 'Kh', '3s', '9d'], 'pot': 40, 'my_bet': 0, 'opp_bet': 0, 'to_call': 0, 'my_stack': 180, 'opp_stack': 180, 'legal_actions': ['check', 'raise'], 'min_raise': 2, 'max_raise': 180, 'raises_left': 4, 'history': [], 'time_left_ms': 75000})
print('Peak RSS:', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 'MB')
"
```

---

## Rules & Sandbox Compliance

- **Python Version:** Python 3.11.
- **Allowed Libraries:** Standard library + NumPy only (no runtime file, network or process I/O).
- **Memory Footprint:** $\approx 96.4\text{ MB}$ RSS steady-state (well within the 1 GB rulebook limit).
- **Time Limits:** 30 s per leg (Stage 1), 75 s per leg (Stage 2); 25% safety bank untouched.
- **State Isolation:** Clean process per leg; no state carries between legs or matches (Rulebook 5.9, 10.3).
