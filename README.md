# Discard Hold'em Bot — Maximum Exploitation & GTO Champion Edition

Python 3.11 tournament bot for the Pokerbots Discard Hold'em tournament (heads-up Texas Hold'em, 3 hole cards, simultaneous exposed discard after the flop).

**Submission:** `bot.py` (single file in the root directory, ~67 KB, standard library + NumPy only).  
SHA-256: `9d9733b3560a2ffbfaff0215f1fd452f010fa24df7b0dee3b141f2441f3a2b6b`

---

## Championship Architecture & Optimization

### 1. Vectorized Memory & Speed Optimization
- **Ultra-low Memory Footprint:** Evaluator arrays and combinatorial meshes run entirely on compact integer datatypes (`np.int16` and `np.int8`) with dot-product hash evaluation.
- **Chunked Exact Solvers:** Turn and flop exact/semi-exact solvers process peer combinations in lightweight chunks, avoiding large temporary array allocations.
- **Peak RAM:** **$63.1\text{ MB}$ RSS** across multi-hundred hand runs (Limit: $1,000\text{ MB} / 1\text{ GB}$).
- **Latency:** Fast vectorized evaluation ($\approx 36\text{ ms}$ for $40,000$ hand comparisons), using only $20.4\text{ s}$ out of $60.0\text{ s}$ combined time bank over 400 hands.

### 2. Threat A Counter: GTO River MDF & Shover-Killer Engine
- **Versus CFR Solvers:** Implements game-theoretic Minimum Defense Frequency (MDF) bluff-catching thresholds:
  $$\text{MDF} = \frac{\text{Pot}}{\text{Pot} + \text{To\_Call}}$$
  Guarantees unexploitable defense against river barrel bluffs while preventing exploitation by balanced solver bots.
- **Versus All-in Shovers:** Automatically identifies hyper-aggressive shoving bots and snaps off wide shoves with $>48\%$ equity, neutralizing erratic random all-in bots.

### 3. Threat B Counter: Maximum Chip Harvesting Engine (Capped Score Maximizer)
Under Rulebook Section 8.3, ties in match points are broken by **Capped Chips per Hand** ($C = 400$ in Stage 1, $C = 1000$ in Stage 2).
- When holding monster equity ($q > 0.88$), the bot shifts into **Accelerated Harvesting Mode** ($1.3\times\text{--}1.6\times$ pot sizing) to rapidly hit the $+400$ or $+1000$ chip cap against weaker field bots.
- Exploits calling stations with massive value overbets, maximizing tie-breaker equity.

### 4. Bayesian Opponent Discard Inferrer (`_opp_discard_consistency`)
In Discard Hold'em, both players publicly reveal their discarded card after the flop:
- Evaluates all $\binom{48}{2} = 1,128$ candidate opponent pairs against their exposed discard in a sub-millisecond vectorized pass.
- Holdings consistent with maximizing flop score receive full weight; contradicted holdings are exponentially discounted.
- Turn and river equity calculations condition on this exact posterior holding distribution.

### 5. Heads-Up GTO Preflop Exploitation Engine
- **Button Dominance:** Opens $\approx 85\%$ of hands from the Button with a 2.0x min-raise to 4 chips ($q \ge 0.44$). Folds only absolute uncoordinated trash.
- **Big Blind Defense:** Defends wide when facing min-raises ($q \ge 0.38$), and 3-bets aggressively with top holdings ($q > 0.62$).

### 6. Flop Continuation-Bet (C-Bet) Texture Engine
- Analyzes flop board texture dynamically:
  - **Dry / Paired Textures:** High-frequency small c-bet sizing ($30\%\text{--}33\%$ pot) on dry boards to exploit preflop range advantage and deny cheap discard realization.
  - **Wet / Connected Textures:** Polarized larger sizing ($60\%$ pot) with made hands and high-equity draws; checks back marginal showdown value.

### 7. Discard Camouflage & Endgame Match-Point Shield
- **Discard Camouflage:** Injects $25\%$ mixed-strategy entropy when two discard candidates are within $1.5\%$ EV of each other, breaking predictable discard patterns.
- **Endgame Match-Point Shield:** When holding a decisive lead ($\ge +150$ chips) in the final $25\%$ of hands in a leg, the bot activates **Shield Mode**: tightens marginal speculative calls and avoids high-variance all-in coin flips to lock in the match win.

---

## Rules & Hardware Compliance

- **Runtime:** Native Python 3.11.15.
- **Dependencies:** Standard library + NumPy only (no SciPy or external packages needed at runtime).
- **File System & Network:** Zero file writes at runtime, zero network requests, zero subprocesses.
- **Hardware Profile:**
  - 1 vCPU compatible (`OMP`, `OPENBLAS`, `MKL`, `NUMEXPR` pinned to 1 thread).
  - Peak RAM footprint: **$63.1\text{ MB}$ RSS** (Limit: $1,000\text{ MB} / 1\text{ GB}$).
  - Startup time: $<0.1\text{ s}$ (auto-calibrates `speed_scale` to match host compute).
  - Safety buffer: $25\%$ reserved time bank untouched.
- **Fair Play:** State is isolated within each leg; no state carries between legs or matches, strictly respecting Rulebook 5.9 and 10.3.

---

## Local Benchmark Summary

See [RESULTS.md](RESULTS.md) for full benchmarks under Python 3.11 against the starter-kit engine and duplicate head-to-head matches.
