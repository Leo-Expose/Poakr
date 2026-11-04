#!/usr/bin/env python3
"""Generate honest v2 evidence summary and checksum-pinned source/test package."""
from pathlib import Path
import ast, hashlib, json, re, zipfile
ROOT=Path(__file__).resolve().parent.parent
(ROOT/'releases/v2/rebuilt').mkdir(parents=True,exist_ok=True)
sha=hashlib.sha256((ROOT/'runtime/bot.py').read_bytes()).hexdigest()
resource=json.loads((ROOT/'evidence/v2/resource_results.json').read_text())
release=json.loads((ROOT/'evidence/v2/release_matches_results.json').read_text())
exhaustive=json.loads((ROOT/'evidence/v2/exhaustive_results.json').read_text())
assert release['runtime_sha256']==sha and exhaustive['runtime_sha256']==sha
assert all(r['runtime_sha256']==sha for r in resource)
assert exhaustive['passed']
log=(ROOT/'evidence/v2/core_tests.log').read_text()
assert log.rstrip().endswith('OK')
count=int(re.search(r'Ran (\d+) tests',log).group(1))
ast.parse((ROOT/'runtime/bot.py').read_text(),feature_version=(3,11))
rows=release['results']; names=['OverFolder','CallingStation','Balanced','Aggressor']
v2={r['opponent']:r for r in rows if r['config']=='v2_release_board'}
v1={r['opponent']:r for r in rows if r['config']=='legacy_v1'}
text=f'''# Pokerbot v2 — measured validation, including regressions

## Verdict

A substantially safer, configurable engineering core is implemented and tested.
**It is not a perfected strategy or an official submission.** The final holdout
favored the preserved v1 in match wins; v2 had higher average chips. Do not replace
match-point evidence with a chip-profit story.

Official custom mechanics, protocol/lifecycle, fair-play interpretation, finals
bank and tie-break cap remain unknown. `docs/v2/READINESS.md` tracks every area explicitly.

## Frozen-release identity

`runtime/bot.py` SHA-256: `{sha}`.

The final unit, resource, exhaustive-frequency and fresh-seed strategy checks use
this release. Older exploratory results are separate and not relabeled as release
evidence. The runtime uses stdlib + NumPy, with no source-package imports.

## Correctness and engineering tests

- **{count}/{count} unittest cases passed**, including independent evaluator
  comparisons, configured variants, exact equity, collisions, public-terminal
  memory, malformed reveals, request replay/conflicts, match resets, watchdog
  restoration, depleted budgets, strict parsing and standalone read-only execution.
- Standard seven-card evaluator versus independent five-subset reference:
  **1,200 random hands, zero mismatches**.
- Generic configured evaluator versus independent reference:
  **800 hands across eight rule configurations, zero mismatches**.
- Exact known-hand flop, turn and river equity checked against independent
  enumeration. Also tested exact preflop equity in a small configured deck.
- **All {exhaustive['hands']:,} standard five-card combinations** reproduce the
  independently known category frequencies. This is frequency validation, not an
  exhaustive seven-card score/tiebreak differential proof.
- Resumable Monte Carlo retains its alpha-spending look count; exact-enumeration
  timeout cannot leak biased prefix equity.
- Python 3.11 grammar check passed. **Execution used Python 3.13.16**, not 3.11;
  the actual required interpreter remains a release gate.

## Constrained-runtime stress

A separate child process was pinned to one permitted CPU, given a **1 GiB virtual
address-space cap**, and denied network/process creation/file-write operations
via Python audit hooks. This is not an OS-level replica of the official sandbox.
Only one synthetic decision per street was requested; real request counts depend
on the variant and action history.

| Hands | Requests / legal responses | Wall time | Peak RSS | Per-decision deadline interruptions |
|---|---:|---:|---:|---:|
'''
for r in resource:
    text+=f"| {r['hands']} | {r['requests']} / {r['legal_responses']} | {r['wall_s']:.2f}s | {r['rss_mib']:.2f} MiB | {r['compute_timeouts']} |\n"
text+='''
Both runs used a 60-second configured bank and retained a 25% planned reserve.
No forbidden operation was attempted and no worker crashed. Deadline interruption
is not a match forfeit: completed Monte Carlo batches may support a decision;
otherwise a supplied legal fallback is selected. Some exact computations can be
abandoned. Accuracy/strength under every possible workload is not established.
Host waiting time and kill semantics still need verification. The 1,000-hand
stress uses 60 seconds conservatively; the announcement does not specify the
actual finals allowance.

## Final fresh-seed strategy holdout

Six matches per opponent, 60 duplicate pairs / 120 hands per match, deal seeds
53000–53005. Synthetic standard-Hold'em policies, not equilibrium opponents.
`v2_release_board` enables replay inference with proactive bluff/risk dial off;
**the default unconfigured adapter leaves replay inference off** until integration
checks authorize it.

| Opponent | Board-enabled v2 wins | v1 wins | v2 mean chips | v1 mean chips |
|---|---:|---:|---:|---:|
'''
for name in names:
    a,z=v2[name],v1[name]
    text+=f"| {name} | {a['wins']}/6 | {z['wins']}/6 | {a['mean_chips']:+.1f} | {z['mean_chips']:+.1f} |\n"
w2=sum(r['wins'] for r in v2.values()); w1=sum(r['wins'] for r in v1.values())
text+=f'''\n**v2: {w2}/24 wins. v1: {w1}/24 wins.** These small samples do not establish
superiority in either direction. The over-folder is a clear unresolved policy
weakness, and v2 lost more matches to it on this holdout. Preserving the baseline
and reporting the regression is preferable to shipping an unsupported “upgrade.”

The benchmark drives `BotSession.act` through a chip-action adapter and feeds
public action histories, including actual capped bet sizing. It never feeds
unrevealed runout or opponent-hole cards into memory. It asserts legality. It
measures the decision core, **not the official wire protocol**. Reported own-compute
time excludes benchmark public-history reconstruction and transport overhead.
Timing-dependent sample caps mean repeated runs need not be bit-identical.

## Earlier exploratory v2 pilot — separate evidence

Seeds 43000–43005, six 60-pair matches per opponent:

- v2 with board inference and proactive bluff: **18/24 wins**.
- v2 with board inference, proactive bluff disabled: **18/24**.
- v2 without duplicate inference: **14/24**.
- Frozen v1 baseline: **16/24**.
- Duplicate-aware mirror: 4/6 wins, mean +236.5 chips, noisy six-match diagnostic.
  Both bots have isolated memory. This is not evidence of a universal advantage
  when both players track, nor proof that mirror bias is absent.

The proactive-bluff pilot did not add wins; it remains off by default. The risk
dial remains off based on its weak earlier evidence. The final seed set is not
silently combined with the exploratory pilot to create a more flattering result.

## Open strategy work

The random-opponent equity model is not a conditional opponent calling/betting
range. Selective betting, trap-heavy behavior, adaptive opponents, future betting,
match-risk utility and the actual capped chip tie-break remain unresolved. No
finite synthetic suite proves optimal poker play. Bigger independent holdouts and
actual-variant tests are required before strategy selection.

## Reproduce

The builder writes `releases/v2/rebuilt/bot.py`; comparisons still evaluate the
frozen `runtime/bot.py`. All benchmark reruns write `evidence/v2/reruns/`. This
report reads preserved historical evidence, not new reruns or a changed candidate.

```bash
python3 bench/build_release.py
python3 -m unittest discover -s tests -v
python3 bench/exhaustive_v2.py
python3 bench/resource_v2.py
python3 bench/matches_v2.py --matches 6 --deals 60 --seed 53000 \\
  --release-check --no-mirror --output release_matches_results.json
python3 bench/package_v2.py
```

See `docs/v2/PROTOCOL_EXAMPLE.md` for fixtures and `docs/v2/READINESS.md` for the complete audit.
The release contains both the v2 integration candidate and the preserved v1.
No claims of guaranteed wins, universal no-forfeit safety, organizer approval,
research novelty or “everything perfected” are made.
'''
(ROOT/'releases/v2/rebuilt/VALIDATION.md').write_text(text)
# Only relevant source, dependencies, evidence and documentation; no caches/binaries.
include=['runtime/bot.py','docs/v2/README.md','docs/v2/READINESS.md','releases/v2/rebuilt/VALIDATION.md','docs/v2/ARCHITECTURE.md','docs/v2/PROTOCOL_EXAMPLE.md',
         'src/__init__.py','src/core.py','src/adapter.py','src/fast_eval.py',
         'legacy/bot_v1.py','legacy/ARCHITECTURE_v1.md','legacy/VALIDATION_v1.md',
         'bench/build_release.py','bench/package_v2.py','bench/exhaustive_v2.py','bench/resource_v2.py','bench/matches_v2.py',
         'bench/fullmatch.py','bench/test_bot.py','bench/test_duplicate_safety.py',
         'engine/cards.py','engine/game.py','engine/equity.py','engine/numpy_eval.py',
         'tests/test_core.py','evidence/v2/core_tests.log','evidence/v2/exhaustive_results.json','evidence/v2/exhaustive.log',
         'evidence/v2/resource_results.json','evidence/v2/resource.log','evidence/v2/matches_results.json','evidence/v2/matches.log',
         'evidence/v2/release_matches_results.json','evidence/v2/release_matches.log',
         'config/example_standard.json','config/example_replay_board.json','config/example_short_deck.json',
         'fixtures/example_session.jsonl']
manifest={'runtime_sha256':sha,'runtime_entry':'runtime/bot.py','official_protocol_verified':False,
          'python_execution':'3.13.16; 3.11 syntax checked, actual 3.11 execution pending',
          'files':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in include}}
(ROOT/'releases/v2/rebuilt/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
include.append('releases/v2/rebuilt/manifest.json')
path=ROOT/'releases/v2/rebuilt/pokerbot_v2_audited.zip'
with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
    for name in include:
        entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)); entry.compress_type=zipfile.ZIP_DEFLATED
        entry.external_attr=0o644<<16; z.writestr(entry,(ROOT/name).read_bytes())
print('Wrote',path,'and releases/v2/rebuilt/VALIDATION.md; runtime checksum:',sha)
