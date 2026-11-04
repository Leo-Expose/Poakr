# Guarantee derivations and proof obligations

## 1. Abandonment with arbitrary known future cost bounds

Let B be the exact score of completed hands. Let the current hand's profit under free abandonment be at least −C and each later hand i's profit be at least −F_i. If scoring is raw additive own net:

`final score ≥ B − C − Σ F_i`.

This follows by summing pointwise lower bounds; it does not depend on opponent strategy, card probabilities, or a learned range. If the lower bound strictly exceeds threshold T, following the specified abandonment continuation guarantees score >T, provided the game actually finishes without forfeiture.

No conclusion follows from a nonpositive bound. It is a sufficient condition, not a necessary characterization of all winning states.

### Per-hand symmetric clipping

For `φ_K(x)=max(−K,min(K,x))`, monotonicity gives:

`x ≥ −C ⇒ φ_K(x) ≥ −min(C,K)`.

Sum these inequalities over unfinished hands and add the **completed clipped scoreboard**, not completed raw profit. This proves the optional cap certificate. A cap on total profit, a cap on average profit, asymmetric rewards, rake, tournament tie-break conventions, and nonlinear score transformations require their own proof. Division by a known positive hand count preserves a zero-threshold sign, but does not justify swapping different cap formulas.

### Arithmetic and costs

Fraction arithmetic gives exact comparisons for the supplied rational inputs. Converting a finite float through its decimal string certifies that supplied decimal, not the physical accuracy of a host's rounded accounting. Prefer organizer-defined integer money ticks or exact decimal amounts.

Suffix sums cost O(H) preparation and O(1) arithmetic operations per query. Rational bit complexity still depends on amount sizes; this is not a constant-bit-complexity claim.

## 2. Safe settlement on a final board

Assume heads-up equal initial stacks, standard matched-payout/refund semantics, no rake/fees, final public board, correct comparison/payout rules, and legal check/call play through settlement. Consider every physically legal opposing holding, including those the posterior considers unlikely.

If the hero's final rank is never below the opponent's, a check/call continuation never folds and never creates a new voluntary raise. Equal initial stacks ensure the hero can match any opposing total contribution within the common stack cap. A matched showdown tie returns the hero's matched stake; uncalled excess is returned to its owner. Therefore hero's current-hand net is at least zero.

If the hero strictly beats every possible peer, a showdown win transfers at least the opponent's already-paid contribution D; future opposing payments can only increase that amount. An opponent fold cannot reduce it under the same contribution/refund semantics. Thus current-hand net is at least D.

Let G be 0 in the tie-capable case or D in the strict-win case. Then:

`final raw net ≥ B + G − Σ F_i`.

For the stated per-hand clipping formula, G≥0 implies the current scored floor is `min(G,K)`.

### The critical continuation distinction

The settlement credit is conditional on **not folding the current hand**. It cannot be used to set the existing immediate-fold lock flag. A future integration must have at least:

1. `SETTLE_SAFE_RIVER`: verify current proof freshness; check/call only, no fold/raise.
2. `ABANDON_FUTURE`: after confirmed hand-end accounting, check/fold later hands.

If a premise changes, the certificate is invalid—not permission to silently call an unsafe hand. A watchdog fallback that folds before settlement would invalidate G; this must be addressed before integration. Rank confidence from a finite opponent model is never a substitute for full physical-peer coverage.

A contract assertion does not prove the actual rules. The frozen runtime has not been modified to execute this new plan.

## 3. Dominating-quads rainbow-turn proof

Assume standard 52-card high poker, two hole cards, a four-card public turn, and exactly one further board card. Own hole cards are both rank R; two public cards are the other two rank-R cards. The other two public ranks are strictly below R and the four public suits are distinct.

The hero already has quads R, which persist on every river. All four cards of rank R are known, so an opponent cannot also make quads R. No higher rank appears on the turn; one river card plus two opposing cards supply at most three copies of any higher rank, hence no higher quads. A rainbow turn plus one river has at most two public cards of a suit; two opposing private cards raise that to at most four, insufficient for a flush or straight flush. Standard high ranking puts all other categories below quads. Therefore the hero strictly wins in every legal private-pair/runout world.

The scalar settlement-credit argument applies through both remaining betting rounds if check/call play, equal-stack matching, standard matched-payout/refund semantics, no fees, correct payouts, and clock completion are verified. It is not a final-board assumption: it is a separate symbolic all-futures rank proof. The test enumerates all 45,540 worlds for one example; the logical proof covers the stated pattern generally. Broader turn/flop patterns remain future research.

## 4. Exact toy-game minimax certificate

For the enumerated Kuhn game, let N_ab be the integer sum of first-player payoffs over six distinct deals for pure strategies a,b. The chance-averaged matrix is `A_ab=N_ab/6`.

For any rational first-player distribution x and second-player distribution y:

`L=min_b Σ_a x_a A_ab` is a achievable expected lower bound;
`U=max_a Σ_b A_ab y_b` is an adversarial expected upper bound.

The lab reconstructs valid nonnegative rational distributions summing exactly to one and verifies all 64 opponent constraints on each side. It obtains `L=U=−1/18`; hence no alternative strategy can improve the first player's worst-opponent expected value in that exact game. Floating LP output proposes candidates; the rational inequalities establish the result.

Own-card/public-history information sets are encoded in each six-bit complete pure strategy. The player cannot pick a different action on two worlds that share its observed information set. Matrix optimization does not inspect the opponent's true card to choose a live action.

### Pointwise and duplicate witnesses

A legal second-player policy that never bets after a check and always calls a bet yields first-player payoff −1 or −2 when first holds the lowest card and second the highest. Every first-player strategy loses on that physical world, even though neither strategy reads the other's actual card.

For the duplicate witness, the opponent bets/calls only with the highest card and otherwise checks/folds. First copy: our lowest card can do no better than −1. Swapped copy: our highest card can collect no more than +1, because the opponent's lowest card contributes no optional money. The total cannot exceed zero. Enumeration of all 64×64 own policy pairs verifies it. This also permits adaptation between copies and more freedom than a single fixed controller.

This is not a numerical theorem about the undisclosed Hold'em variant. It refutes an unrestricted promise spanning every poker world, and demonstrates why chance-averaged optimality is not an every-match winning certificate.

## 5. Claims intentionally excluded

No theorem here establishes clock survival under arbitrary scheduling/traffic, arbitrary modified ranking/payout rules, no forfeits under malformed unknown protocols, tournament qualification, global research novelty, or universal initial-state victory. Those require different specifications and evidence.


## Standard-Hold’em witness against strict universal initial-state victory

This is a separate witness, not a claim about the unpublished modified rules. In standard heads-up high Hold’em with equal hand-start stacks, matched/refunded contributions, no rake/fees, and raw-net scoring, consider a physically legal chance realization in which every hand's public board is a royal flush. Choose private cards disjoint from that board. Repeating such deals across hands is legal when the deck is reshuffled; duplicate seat swaps preserve the royal board.

A legal opponent that checks when free and calls every wager never folds. If the hero reaches showdown, the shared board ties and returns matched contributions: hero net is zero. If the hero folds earlier, hero net is nonpositive. Equal stacks allow the opponent to match every legal wager. Hence every hero policy has nonpositive total net in this world, including randomized policies on every realized random path. Strict positive-net victory against every opponent and every legal deal sequence is therefore impossible in this explicitly defined standard game. The specifically defined symmetric per-hand clipping also preserves this nonpositive sign.

This does **not** prove that every policy must lose, that nonloss is impossible, that poker skill is irrelevant, or that a conditional positive-margin certificate is impossible. It identifies exactly why unrestricted strict victory and verified winning state regions are different targets.


## Implemented composition controller

The conditional safe-settlement/future-abandonment composition is now implemented separately in `research/guarantee_lab/settlement.py`. See [controller invariants and induction](CONTROLLER.md). Verified actual accepted actions, correct host results/rules, and completion without forfeit remain premises; the controller does not turn declarations into self-authenticating facts.
