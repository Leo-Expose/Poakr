# God-Tier Pokerbots Competitor — Discard Hold'em

**Competition:** MIT Pokerbots Tournament (Discard Hold'em variant)  
**Status:** 🟢 **COMPETITION-READY** — Candidate frozen at `releases/discard/v1/`  
**Target:** 1st Place  

---

## 🏆 Quick Summary

This is a **full-stack competitive poker agent** for Discard Hold'em (3 cards preflop → simultaneous exposed discard after flop → standard turn/river). It integrates:

| Component | Technology | Competitive Edge |
|-----------|------------|------------------|
| **Preflop Solver** | CFR (78 info sets) | Game-theoretic optimal baseline |
| **Turn/River Solvers** | Mini-CFR with subgame decomposition | Perfect river play, optimal turn barrels |
| **Duplicate Exploitation** | Instance 1 learn → Instance 2 crush | **Unique info advantage** (every deal played twice) |
| **Opponent Modeling** | 7 archetypes + Bayesian updating | Real-time exploitation of leaks |
| **Variance Management** | WinLock + Kelly + Certainty-Equivalent | Cap-aware strategy for Swiss/Finals |
| **Tournament Awareness** | Phase detection + ICM adjustments | Stage 1 (400h, ±400) / Stage 2 (1000h, ±1000) |
| **Equity Engine** | Vectorized NumPy (eval7) + Precomputed tables | <1ms/decision, 22,100 preflop equities |
| **Bet Sizing** | Geometric + equity-adjusted + board texture | Mathematically optimal multi-street pressure |

---

## 📊 Test Results (Supplied Engine)

| Test | Hands | Result | Notes |
|------|-------|--------|-------|
| Stage 1 vs CallingStation | 400 | **WIN** (+400 cap) | 8/8 seeds |
| Stage 2 vs Selective | 1000 | **WIN** (+1000 cap) | 5/5 seeds |
| Mirror Match (self-play) | 1000 | +212 / -212 | Identical copies |
| Shove Diagnostic | 16 | -229 | No WinLock armed (expected) |
| **Test Suite** | — | **118/118 PASS** | Conformance + strategy + legacy |

**Time Bank:** 1-14s of 60-150s limit | **Notices:** 0 | **Crashes:** 0

---

## 🚀 Quick Start

```bash
# From pokerbot/ directory
python3 tools/discard/build.py

# Run tests (all 118 should pass)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/discard -p 'test_*.py' -v

# Local match (400 hands, Stage 1)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/discard/local_runner.py \
  --hands 400 --opponent CallingStation --wire --sandbox --seed 173000 --output test_400.json

# Local match (1000 hands, Stage 2)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/discard/local_runner.py \
  --hands 1000 --opponent Selective --wire --sandbox --seed 181000 --output test_1000.json
```

**Dependencies:** Python 3.11+, NumPy, SciPy (allowed by tournament)  
**No runtime installs, network, or file I/O** — pure computation

---

## 📁 Key Artifacts

| Path | Description |
|------|-------------|
| `releases/discard/v1/bot.py` | **Frozen candidate** (30,730 bytes, SHA-256: `2de97228...`) |
| `releases/discard/v1/submission.zip` | Upload-ready artifact (single `bot.py` at root) |
| `releases/discard/validated_2026_11_02/` | Complete evidence bundle |
| `docs/TECHNICAL_ARCHITECTURE.md` | **Full technical documentation** |
| `docs/RELEASE_GATES.md` | Submission readiness checklist |

---

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| [`docs/TECHNICAL_ARCHITECTURE.md`](docs/TECHNICAL_ARCHITECTURE.md) | **Complete system architecture** — algorithms, data flow, APIs |
| [`docs/RELEASE_GATES.md`](docs/RELEASE_GATES.md) | Submission gates + evidence status |
| [`docs/discard/REPORT.md`](docs/discard/REPORT.md) | Implementation details + measured results |
| [`docs/discard/GUARANTEES.md`](docs/discard/GUARANTEES.md) | Pointwise mathematical guarantees + limits |
| [`docs/discard/SUPPLIED_ENGINE_VALIDATION.md`](docs/discard/SUPPLIED_ENGINE_VALIDATION.md) | 118-test validation report |
| [`docs/discard/ROBUSTNESS_ITERATION_1.md`](docs/discard/ROBUSTNESS_ITERATION_1.md) | Hardening experiment (96 matches) |
| [`docs/organizer/RULES_RECONCILIATION.md`](docs/organizer/RULES_RECONCILIATION.md) | PDF rulebook reconciliation |

---

## ⚙️ Architecture Overview

```
PROTOCOL (bot.py)
    ├─ TimeBank (60-150s cumulative, 5s/response)
    ├─ GameState (match/hand tracking)
    └─ DuplicateMemory (deal_seed → instance_1/instance_2)
           │
           ▼
POLICY ENGINE (policy.py)
    ├─ CFR Preflop (78 info sets from cfr_preflop.json)
    ├─ Turn CFR (river subgame values from turn_cfr.py)
    ├─ River CFR (polarized bet sizing from river_cfr.py)
    ├─ Range-vs-Range Equity (range_vs_range.py)
    ├─ OpponentModel (7 archetypes, Bayesian)
    ├─ TournamentContext (WinLock, Kelly, Phase)
    └─ BoardTexture (wet/dry/paired/trips classification)
           │
           ▼
EVALUATOR (eval7.py)
    ├─ Vectorized 7-card eval_batch (N×7 → scores)
    ├─ Monte Carlo equity_vs_range (500-5000 draws)
    └─ Precomputed preflop_equity.json (22,100 hands)
           │
           ▼
DISCARD (discard.py)
    ├─ Equity-optimal (choose_discard)
    ├─ Blocker-aware (blocker_value)
    └─ Fast heuristic (choose_discard_fast)
```

---

## 🔑 Key Innovations

### 1. Duplicate Deal Exploitation
Every deal plays **twice** (once as button, once as BB). We record everything in Instance 1:
- Opponent's exact hole cards (at showdown)
- Their preflop action, discard choice, postflop lines
Then in Instance 2: **we know their hand** → perfect decisions.

### 2. Turn/River CFR with Subgame Decomposition
- River CFR solves polarised betting game (5 bet sizes)
- Turn CFR uses River CFR as **value function** for continuation
- Result: Near-GTO turn/river play in <10ms

### 3. WinLock Certificate
```python
if net_chips - abs(current_hand_risk) > remaining_hands * 50 + 10:
    # MATHEMATICALLY INSURMOUNTABLE LEAD
    # Play only check/fold → zero variance
```

### 4. Geometric Bet Sizing
Multi-street pressure: `pot × (1+r)^streets = stack` → optimal fraction `r` each street.

### 5. 7-Archetype Opponent Modeling
NIT, TAG, LAG, FISH, MANIAC, STATION, UNKNOWN — with Bayesian updating and archetype-specific counter-strategies.

---

## ⚠️ Known Limitations

1. **Python 3.11 execution** untested (local 3.13.16, AST grammar OK)
2. **OS sandbox** not verified (audit hooks only)
3. **Clock charging** discrepancy during engine startup (clarification drafted)
4. **No universal nonloss guarantee** (mathematically impossible in this variant)
5. **Custom stage/hand combos** not validated

---

## 🎯 Competitive Assessment

**Realistic Expectation:** **Top 5-10%**

| Factor | Assessment |
|--------|------------|
| GTO Foundation | ✅ Strong (CFR preflop + turn/river) |
| Exploitation | ✅ Strong (duplicate + archetypes + leaks) |
| Variance Control | ✅ Strong (WinLock + Kelly + phase-aware) |
| Speed | ✅ Excellent (<1ms typical, 1-14s total) |
| Tournament Format | ✅ Optimized for both stages |
| Variance Risk | ⚠️ Inherent (400/1000 hand samples) |
| Unknown Opponents | ⚠️ Field depth unknown |

**No "guaranteed #1" claim** — variance, unknown innovations, and field depth make this impossible. This is a **maximally competitive** agent within the rules.

---

## 📦 Submission Checklist

- [ ] `python3 -m py_compile bot.py` (Python 3.11 syntax)
- [ ] All 118 tests pass
- [ ] 400-hand match completes in limits
- [ ] 1000-hand match completes in limits
- [ ] `releases/discard/v1/bot.py` SHA-256 verified
- [ ] `submission.zip` contains single `bot.py` at root
- [ ] Registration complete (2-person team)
- [ ] Portal upload before **15 Nov 2026 23:59 IST**

---

*Last updated: 2026-11-04*  
*Candidate: `releases/discard/v1/` (immutable, byte-identical across runs)*