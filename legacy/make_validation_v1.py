raise SystemExit("Historical generator retired. Use bench/package_v2.py")
#!/usr/bin/env python3
"""Summarize completed paired benchmarks and package the reproducible prototype."""
import json, math, statistics, hashlib, ast, zipfile
from pathlib import Path
root = Path(__file__).resolve().parent.parent
raw = json.loads((root/'bench/holdout_results.json').read_text())
rows = raw['results']; n = raw['matches']

def wilson(w,n):
    z=1.96; p=w/n; den=1+z*z/n
    m=(p+z*z/(2*n))/den
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return f'{100*(m-h):.1f}–{100*(m+h):.1f}%'

def group(dup,risk):
    return {r['opponent']:r for r in rows if r['duplicate']==dup and r['risk']==risk}
full, no_dup, neutral = group(True,True),group(False,True),group(True,False)
sha=hashlib.sha256((root/'runtime/bot.py').read_bytes()).hexdigest()
ast.parse((root/'runtime/bot.py').read_text(),feature_version=(3,11))
text = '''# Hardened pokerbot — validation report

## Bottom line

The integrated duplicate-inference layer materially improved results in this
local test suite. The system is **not perfected or tournament-ready**: the official
variant/protocol still need integration, one synthetic opponent exposes a leak,
and the risk dial has no demonstrated robust advantage.

## Fresh-seed paired benchmark

- 16 matches per opponent; **100 duplicate pairs / 200 hands per match**.
- Same deal seeds across configurations: 23000–23015.
- Synthetic opponents, local standard-Hold'em engine, match points = 1 win,
  0.5 draw, 0 loss. There were no draws in this run.
- Persistent RNGs, per-match state resets, street-index conversion, actual
  configured raise limits, public-history learning, legal-action assertions.
- The tracker receives only cards present in our requests, not unrevealed runouts.

| Opponent | Duplicate + risk dial | No duplicate + risk dial | Duplicate + neutral dial |
|---|---:|---:|---:|
'''
for name in full:
    text += f"| {name} | {full[name]['wins']}/16 | {no_dup[name]['wins']}/16 | {neutral[name]['wins']}/16 |\n"
text += '\n### Mean net chips per match\n\n| Opponent | Full | No duplicate | Neutral dial |\n|---|---:|---:|---:|\n'
for name in full:
    text += f"| {name} | {statistics.mean(full[name]['nets']):+.1f} | {statistics.mean(no_dup[name]['nets']):+.1f} | {statistics.mean(neutral[name]['nets']):+.1f} |\n"
text += '\n### Aggregate observations\n\n'
for label,g in [('Full',full),('No duplicate',no_dup),('Neutral dial',neutral)]:
    w=sum(r['wins'] for r in g.values()); total=n*len(g)
    text += f'- **{label}: {w}/{total} wins ({100*w/total:.1f}%).**\n'
text += '''
These are descriptive fractions over four chosen synthetic opponents, not an
estimate of the tournament population. The risk dial's 53-versus-52 win difference
is insufficient evidence of a meaningful benefit. Do not equate higher chip
expectation with greater match-point performance.

The over-folder result remains weak (8/16 wins). The next policy experiment should
test proactive, observation-supported fold-equity exploitation on fresh seeds,
without sacrificing robustness against aggressive or duplicate-aware opponents.

### Per-opponent win-rate uncertainty (full policy)

95% Wilson intervals, descriptive within this synthetic setup:

'''
for name,r in full.items():
    text += f"- {name}: {wilson(r['wins'], n)}.\n"
text += '''
No guarantees of tournament dominance, Nash-optimality, research novelty, or
organizer approval follow from these tests.

## Correctness fixes made in this iteration

1. **Removed unsafe preflop adjacency inference.** Back-to-back replay does not
   identify pair phase. Only an explicit duplicate-pair ID can enable preflop
   inference, after replay evidence has accumulated.
2. **Rejected impossible and ambiguous inferences.** Check card overlap, all
   shared runout cards, and unique candidate hands.
3. **Made known-hand equity self-contained.** No `engine.cards` import remains
   in the shipped runtime. Exact flop/turn/river enumeration uses embedded NumPy;
   preflop remains sampled.
4. **Stopped fabricating 50% equity on errors.** Invalid cards raise; the decision
   caller falls back to the hidden-information policy.
5. **Fixed known-hand calls.** Use pot odds, not a 52% equity cutoff.
6. **Respected legal sizing.** The benchmark asserts legality rather than allowing
   the game engine to silently repair invalid bot actions.
7. **Fixed observation contamination.** Legal-action lists no longer train the
   opponent model. Only explicit structured opponent responses are accepted by
   the shell's learning hook.
8. **Added a structured showdown kill switch.** Matching hand IDs and explicit
   opponent-hole reveals can invalidate an inference. Opaque protocols do not
   support this verification automatically.
9. **Charged known-hand compute to the bank; added exhausted-bank safe exit.**
10. **Fixed remaining-count direction.** More hands remaining must not imply
    greater endgame urgency. The fallback total of 400 still requires official
    configuration.

## Local safety and speed

- `bench/test_duplicate_safety.py`: **24/24 assertions passed**.
- Includes randomized independent hands, phase ambiguity, card collisions,
  divergent turns, ambiguous matches, showdown contradiction, repeated-hole
  boundaries with explicit IDs, pot odds, restricted sizing, depleted compute
  budget, and isolated single-file execution.
- Exact equity was compared with an independent five-card-subset reference on
  flop, turn, and river.
- 400 exact-flop equity calls: approximately **2.14 seconds** locally.
- Basic shell harness: 72/72 returned legal/blank tokens; decision sanity and
  basic 400-request time test passed. This is not a universal forfeit guarantee.
'''
compute=sum(r['compute_s'] for r in full.values())/(n*len(full))
text += f'- Full-policy average recorded equity compute: **{compute:.2f} seconds per 200-hand synthetic match**. This excludes startup, much policy overhead, and opponent computation.\n'
text += '''- Python 3.11 grammar check passed; tests actually executed on Python 3.13.
  Execution under the organizer's Python 3.11 environment remains required.

## Release gates — still open

- Obtain official rules, deck/ranking modifications, protocol schema, runner,
  persistence model, time accounting, and scoring details.
- Confirm that replay means identical cards with swapped seats and that retaining
  one's observed cards complies with organizer rules. Board replay alone does
  not prove hidden-hole swapping.
- Replace the flexible parser with an exact official-protocol adapter; verify
  output sizing and terminal/control-message handling.
- Validate on the actual variant. The shipped evaluator currently assumes a
  52-card deck, two hole cards, five board cards, and standard ranking.
- Expand opponent coverage: duplicate-aware, adaptive, trap-heavy and stronger
  range-aware policies; test censored, delayed, nonadjacent and reordered replays.
- Independently retest any new over-folder strategy and risk-dial calibration.

## Reproduce / inspect

```bash
python3 bench/test_bot.py
python3 bench/test_duplicate_safety.py
python3 bench/fullmatch.py --matches 16 --deals 100 --seed-base 23000 \\
  --aggressor --risk-ablation --output holdout_results.json
```

`runtime/bot.py` is the deployment file. Runtime dependencies: stdlib + NumPy only.
`pokerbot_hardened.zip` includes it plus this report, the architecture notes, raw
logs/results, and the minimal offline engine required to rerun the benchmarks.

'''
text += f'Runtime SHA-256: `{sha}`.\n'
(root/'VALIDATION.md').write_text(text)
readme='''# Hardened pokerbot prototype

Deployment file: runtime/bot.py (standalone; stdlib + NumPy).
Run: python3 runtime/bot.py

Read VALIDATION.md before submission. Official custom rules and the wire protocol
are NOT yet verified. Local wins do not guarantee competition wins or legality.
The runtime uses Python 3.11-compatible syntax; local tests ran on Python 3.13.

The included benchmarks need only stdlib + NumPy and the included offline engine.
No installation or network access is performed by the bot.
'''
(root/'README.md').write_text(readme)
include=['runtime/bot.py','README.md','VALIDATION.md','ARCHITECTURE.md',
         'bench/test_bot.py','bench/test_duplicate_safety.py','bench/fullmatch.py',
         'bench/make_validation.py','bench/fullmatch.log','bench/fullmatch_results.json',
         'bench/holdout.log','bench/holdout_results.json','bench/bot_safety.log',
         'bench/duplicate_safety.log','engine/cards.py','engine/game.py','engine/equity.py',
         'engine/numpy_eval.py']
with zipfile.ZipFile(root.parent/'pokerbot_hardened.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in include: z.write(root/name,name)
print('Wrote VALIDATION.md and pokerbot_hardened.zip')
