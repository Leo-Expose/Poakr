# Discard Hold’em pointwise guarantees

## Scope

These are sufficient winning-state certificates under the supplied standard-high Discard Hold’em mechanics, valid own/public cards, correctly reconciled integer contributions and raw score, legal execution, and completion without forfeiture. They quantify over **every physically possible retained opposing pair, future river where relevant, and opposing betting/discard strategy**, not a posterior-truncated range. They do not force entry into a winning state from an initial deal.

Both public discarded cards must be dead. Uniform-pair policy estimates are a separate approximation and never establish these guarantees.

## 1. Exact future forced cost

For n future hands, alternating blinds 1 and 2 give:

`F = 3 * floor(n/2) + (n mod 2) * next_own_blind`.

A check-when-free/fold-when-priced policy loses at most these posted blinds. Current paid contribution C is separate. With completed raw score B, immediate abandonment has final raw lower bound `B − C − F`. Strict positivity wins the match under Rulebook 8.1, provided no forfeiture occurs.

This uses no unverified wire-supplied `banked_net` or contract flag. The candidate derives B from hand results independently checked against complete public histories and revealed showdown cards.

## 2. New public-dead-card turn proof

Let the hero hold two cards of rank R, and the four-card public turn contain the other two cards of R. Hero has persistent quads. It suffices to rule out the only stronger possibilities: higher quads and straight flushes.

### Higher quads obstruction

A higher rank absent from the turn can appear at most three times in the opponent’s final seven cards: one river plus two private cards. If a higher rank is present on the turn, a known blocked card of that rank prevents all four cards from being available. Thus every higher public rank must have a card blocked by known own/dead cards.

### Straight-flush obstruction

There are exactly 40 standard five-card suited straight windows: ten per suit including the wheel. A final opposing straight flush must use at least two cards already on the turn: the river plus two private cards supply at most three missing cards. For every window containing at least two turn cards, require at least one of its cards to be blocked by our holding or either public discard.

These two checks imply every final peer loses to our quads. The runtime uses fixed-size 52-bit masks and at most 13 rank / 40 straight-window checks, **not runout enumeration**.

### Two tested enlargements over the old sufficient predicate

1. Hero `9c 9d`; turn `9h 9s 2c 3c`; public discards `4c Ah`. The turn is not rainbow. The only straight-flush windows containing both low clubs require `4c`, which is dead. The old rainbow-only predicate rejected this state; the new proof certifies it.
2. Hero `9c 9d`; turn `9h 9s Ac 3d`; public discards `4c Ah`. The public ace would previously prevent certification. Dead `Ah` prevents higher ace quads, and the rainbow board cannot support a final opposing straight flush.

For each example, tests independently enumerate **C(44,2) × 42 = 39,732** legal opposing-pair/river worlds and compare ranks with the separate frozen configurable evaluator. Every comparison is a strict hero win. Total across these two examples: **79,464 worlds**.

Counterexamples just outside the conditions are retained. Without dead `4c` in example 1, opposing `5c 6c` and river `4c` make a straight flush. Without the dead ace in example 2, the remaining aces can make higher quads.

## 3. All-physical-pair river credit

After the discard, two hero cards + five board cards + two public discards leave 43 cards available for the peer: **C(43,2)=903** retained pairs. Compare every one, without dropping low-probability holdings.

- If any beats the hero: no no-loss credit.
- If some tie and none beat the hero: current hand net at least zero under legal no-fold check/call continuation and matched payouts.
- If every peer loses: current net at least D, the opponent’s already-contributed amount.

With safe current net G, `B + G − F > 0` is sufficient. The candidate keeps checking/calling the current hand until a reconciled payout. It never folds immediately using a not-yet-banked credit.

The same physical river rank pass also supplies exact equity against a **uniform retained-pair model**. That model is not guaranteed to match the opponent’s discard/betting-conditioned distribution. Reusing this pass avoids a redundant strategy Monte Carlo calculation.

## 4. Preserve a certified floor while seeking the MATCH cap

The real tie-break clips match totals, not hands. A plain hard lock can stop with a tiny guaranteed raw lead, sacrificing secondary score. The new candidate permits carefully bounded further play without decreasing the **initial certified lower floor**.

When the initial safe plan certifies lower bound L>0, protect `R=min(L, match_cap)` (or all of L in passive-only mode). Do not reduce R later. After any pending safe hand is paid, a normal hand with B banked and future blind cost F has commitment ceiling:

`M = min(200, B − F − R)`.

Never call or raise if that would make current total own contribution exceed M. If priced beyond the ceiling, fold; if free, checking is legal. Then even losing every committed chip leaves `B − current_paid − F >= R > 0`.

Induction across later hands preserves R: the next posted blind is already included in F. New realized surplus (for example, a free check-through win or an opponent folding its blind) may fund additional play, but the protected floor is not spent. No rank model or equity estimate can override this monetary ceiling.

If the abandonment floor already reaches C, stop spending: final net at least C saturates that match’s tie-break contribution. There is no ranking benefit from earning beyond C in that match.

**Not claimed:** this maximizes expected tie-break score or dominates a passive lock on every realized deal/opponent policy. It preserves the certified floor, not the counterfactual passive policy’s realized winnings. Extra play can fail to improve the cap score, and the remaining ordinary policy is not equilibrium-optimal.

## 5. Concrete endgame fixture

A legal earlier ledger loss supplies B=−60. In hand 2 of a four-hand test, `9c 9d` on `9h 9s 2c 3c` with public dead `4c Ah` faces 20 to call: hero paid50, opponent paid70. Two future hands cost at most 1+2=3.

The new proof certifies `−60 + 70 − 3 = +7`. The candidate calls, checks the river, validates the +70 payout, then protects a final lower floor of +7. This is a finite endgame fixture, not a claim to force that board or deficit/comeback in a tournament.

A separate test shows realized free surplus can be spent only above the protected floor, even against a later all-in raise. All small monetary-loss combinations tested preserve the algebraic bound.

## 6. Strict universal initial-state victory is impossible in this actual variant

Consider legal repeated duplicate deals whose public board is a royal flush. Both players’ original three-card holdings are disjoint from the board. A legal opponent always checks/calls and discards an available private card. Any hero that reaches showdown ties using the shared royal; folding produces nonpositive net. Equal reset stacks let the opponent match every legal wager. Repeating these legal chance realizations makes total hero net nonpositive for every hero policy, including each realized randomized path.

This is a Discard Hold’em witness, not just the earlier toy game. It rules out **strict victory in every legal world**. It does not by itself rule out all possible universal nonloss strategies. Our current candidate does not have such a nonloss guarantee: the recorded 16-hand shove diagnostic loses229 chips, and an identical copy loses212 in the supplied-engine1000-hand mirror.

## Limits

Successful completion and correct rules/host facts remain premises. Fees, a changed Problem Statement, malformed/contradictory host messages, forfeiture, or incorrect accounting invalidate a chip-bound claim. Detecting inconsistency withdraws certification and uses legal recovery; it is not an authentication or OS clock theorem. The 1-November Problem Statement and supplied starter engine have now been checked without changing candidate bytes: [validation](SUPPLIED_ENGINE_VALIDATION.md). This is not validation of the actual Python3.11 tournament host, OS sandbox, or worst-case clocks. Supplied clock charging differs during the startup window; independent raw measurements do not exploit it.
