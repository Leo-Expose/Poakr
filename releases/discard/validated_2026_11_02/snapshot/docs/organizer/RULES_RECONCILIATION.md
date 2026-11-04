# Supplied organizer PDFs — reconciliation, 2 November 2026

These user-supplied PDFs replace the earlier missing-specification assumptions. Original PDF bytes and SHA-256 identities are preserved in `attachments/manifest.json`. Extracted Markdown is a convenience; the PDFs are authoritative. Extraction used a local standard-library parser, not a network service or installed dependency.

- [Rulebook PDF](attachments/5869f741-8421-4b25-b948-1ad66e1e1316.pdf) / [extracted text](attachments/5869f741-8421-4b25-b948-1ad66e1e1316.md)
- [Protocol PDF](attachments/497da9d5-f0da-442b-b739-b5c06f15fe9b.pdf) / [extracted text](attachments/497da9d5-f0da-442b-b739-b5c06f15fe9b.md)

- [Problem Statement PDF, 1 November](attachments/8a894a3d-946f-40e9-b7ab-7c4e01eb0d4c.pdf) / [extracted text](attachments/8a894a3d-946f-40e9-b7ab-7c4e01eb0d4c.md)
- Supplied starter-kit source: `vendor/organizer/Starter_Kit/`; exact Markdown/file hashes in `vendor/organizer/manifest.json`. Original combined Markdown is preserved alongside it.

## Corrected facts

| Area | Supplied specification | Consequence |
|---|---|---|
| Variant | Discard Hold’em, three starting hole cards; simultaneous face-up discard after flop betting | Old two-hole CORA/v2 are NOT compatible game candidates. No old win rate transfers. |
| All-in | Discard still happens after the flop even when all-in | Must answer mandatory discard requests; cannot simply run to showdown with three private cards. |
| Final ranking | Best five from two retained hole cards and five board cards, standard high ranking | Standard seven-card evaluator is applicable only after selecting a pair. |
| Dead cards | Both discarded cards public and removed | Block own discarded card and opposing discard in all hypothetical samples and exact physical-pair enumeration. |
| Betting | 200 reset stacks; blinds 1/2; alternating seats; button first preflop, second thereafter; four aggressive actions per street, BB counts preflop | Independent history replay uses these mechanics; remaining compulsory costs are an exact alternating blind suffix. |
| Amounts | History call/raise amounts and outgoing raise amount are street-total TO amounts | Do not transmit old increment-based `bet/pay` messages. Outgoing call has no amount. |
| Match winner | Greater total raw net chips; equal net draw | Positive raw match net certifies a win, conditional on completion/no forfeit. |
| Tie-break | Sum of clipped **match** nets divided by total hands, C=400 qualifier / C=1000 finals, provisional | Existing per-HAND clipping lab is an abstract contract only, NOT this official tie-break. |
| Time bank | 60 s / 400 hands; 150 s / about 1000 hands, provisional | Finals allowance is now known, subject to announcements. |
| Charged interval | Sending action/discard request to complete flushed reply; input waiting and startup not banked | External measurement records raw serialized request/reply time, conservatively including loading delay in its first reply; supplied runner charging differs during its first five seconds. See [clarification](CLOCK_CLARIFICATION.md). |
| Other clocks | 5 s startup; 5 s single reply; 180/450 s whole-match wall kill, provisional | Separate startup, request and complete-match checks are needed. |
| Lifecycle | Fresh process per match, no cross-match state | `init`, `new_hand`, requests/results, notices and `match_end` implemented; ignore unknown types/fields. |
| Failures | Illegal action corrected to check/fold; illegal discard corrected to lowest rank, suit tie order spades/hearts/diamonds/clubs | Runtime does not rely on corrections. Fallback discard matches that suit order, not internal card encoding. |
| Forfeit | Match loss; opponent’s match result +C; both forfeit in same hand draw/0 | Chip-margin proofs do not override forfeiture. Loser’s tie-break delta in a unilateral forfeit is not explicitly specified. |
| Upload | Single bot.py or ZIP with bot.py at root, <=5 MB | New candidate is a 30,730-byte self-contained file using stdlib + NumPy. The whole research workspace ZIP is NOT an upload. |
| Deadline | 15 November **2026**, 23:59 IST | Announcement year is now resolved. |
| Tournament | Usually six Swiss rounds; 7–8 if >about 1000 teams; <about64 round robin, <=32 qualifier skipped; finals top32 RR | Preserve these qualifications rather than assuming six rounds for every field size. |
| Conduct | Own work; published algorithms/standard libraries permitted; no copying bot repositories, collusion, network or exploiting evaluator | No duplicate identification/inference, hidden-input consumption, or runtime file/network/process access in the new candidate. |

## Newly resolved gates

The 1-November Problem Statement is present and reconciled. Its worked examples now run as regression tests. The supplied starter engine completed six full matches, with clocks enabled and unchanged candidate bytes: [validation report](../discard/SUPPLIED_ENGINE_VALIDATION.md).

Duplicate allocation is explicit: the positional three-card holdings and board remain fixed for the two hands; the bots exchange positions. This replaces the earlier ambiguity. Candidate decisions do not infer duplicate identities or use the mapping to recover private information.

Vendor source is unchanged and reconstructed from supplied Markdown, not an independently verified original ZIP. Two tests use the direct unmodified CLI; four use external measurement/resource wrappers, not a modified vendor source file.

## Remaining genuine gates

1. Actual **Python3.11 / organizer NumPy image**: local execution remains3.13.16; grammar checks are not execution tests.
2. **OS-enforced sandbox**: affinity, 1-GiB address-space limits and audit checks do not prove read-only mounts, network namespaces, native-code isolation or adversarial scheduling behavior.
3. **Clock clarification**: supplied engine excludes responses within its first five seconds from charging; independent raw timing passes finite checks. [Draft report](CLOCK_CLARIFICATION.md) has not been sent.
4. **Provisional amendments**: confirm final limits/banks/caps; future fees/antes/changed rules must not be assumed away.
5. **Strategy strength**: finite starter/random wins and exact conditional certificates do not establish a minimax solution, tournament win rate or qualification guarantee. An identical candidate loses212 in the mirror run.
6. Actual registration, eligibility and final valid portal upload remain the team's responsibility; no upload has been performed.

Earlier reports and frozen archives remain unchanged historical research. Their missing-specification statements describe their original state. Current implementation: [Discard Hold’em report](../discard/REPORT.md).
