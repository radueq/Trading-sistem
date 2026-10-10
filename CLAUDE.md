# CLAUDE.md

Python trading/backtesting system. Multi-spec remediation engagement
(#003 Outcome-Aware Evaluation + #004 Hypothesis Generation), staged
implementation plan. Primary working branch: `claude/spec004-audit`.

## Source of truth -- read these, don't ask

- `docs/decision_sheet_003_004_2026-10-05.md` -- Technical Decision
  Registry. Per-item acceptance status, lettered sections (A, B, C...)
  for decision records, append-only "Revision N --" notes at the top.
- `docs/implementation_plan_003_004_2026-10-05.md` -- stage sequencing.
  Its top "Status:" block states what's authorized / delivered /
  accepted RIGHT NOW. Read it before assuming what stage you're on.
- `docs/joint_remediation_design_003_004_2026-10-04.md` -- the actual
  algorithms and designs, already closed. Implementation must match
  this exactly; this is not a space to redesign from first principles.

These three files ARE the state of the engagement, not the chat
history. A fresh session with no conversation memory can and should
reconstruct the current state entirely from them plus `git log`.

## Roles (three-axis delegation)

- **Radu** -- contractual/strategic/scope decisions and authorization
  only. He relays GPT's technical verdicts verbatim, in Romanian --
  that text is GPT's voice, not Radu's own. Radu's own voice is
  authorization, stop conditions, and scope calls.
- **GPT** -- independent technical reviewer. Verifies by direct
  execution (reproducing numbers, running `resolve_name()`-style
  checks), never by reading prose alone. Gives ACCEPTED or CHANGES
  REQUIRED verdicts, scoped precisely.
- **Claude** -- implements, verifies, delivers a bundle for GPT's next
  review.

## Authorization discipline -- the rule that matters most

Never start work beyond what Radu explicitly authorized in his own
message -- not even one line away (same file, same bug pattern, the
obvious "next" item in the plan). **An acceptance of stage N is NOT
authorization for stage N+1** -- GPT states this explicitly on nearly
every acceptance; treat it as a hard rule, not formality. Concrete
example already in this repo: TEST 49 (`tests/spec004/test_49_
evaluation_cannot_import_hypothesis.py`) shares the IDENTICAL bug and
fix as TEST 26, but belongs to Stage 7, which stays untouched until
separately authorized -- "shares the algorithm" is not authorization
to also fix it now. If authorization is ambiguous, ask; don't infer
from plan order or thematic proximity.

## Verification discipline -- mandatory before claiming any fix

1. Reproduce the claimed bug/behavior directly by execution, not hand
   derivation, before writing the fix.
2. After fixing, temporarily revert to the old/wrong behavior and
   confirm the regression test fails with CONCRETE evidence (the exact
   wrong value/output printed, not just "it fails"). Confirm nothing
   else breaks as collateral.
3. Restore, reconfirm green.
4. State exactly what was verified and how -- never a bare "fixed."

This has caught real self-authored bugs repeatedly, not hypothetically
-- e.g. Stage 4's bootstrap iteration-identity bug, Stage 5's missed
alias-candidate construction, and Stage 5 round 2's single-package-
tuple-context relative-import bug (reasoning that turned out wrong
even after "verification," caught only because GPT re-derived it by
execution). Skipping this step is not a shortcut; it's exactly where
bugs survive.

## Never overclaim

- "Fixed" / "accepted" / "verified" must name the exact scope --
  "ACCEPTED in the verified scope," never a bare "accepted."
- A passing test is not proof of whatever it doesn't actually assert.
  Re-read what a new test really exercises before citing it as
  coverage (Stage 4 round 3 caught its own `if horizon_bars == 1`
  guard that silently never ran, passing vacuously).
- If something is genuinely out of reach this round, record it as an
  open item -- never force a weaker version silently to call it done.
- A prose summary in a design doc can itself be wrong. When a claim
  can be checked by running real code (`importlib.util.resolve_name`,
  exact arithmetic, an actual test execution), check it -- don't trust
  the written explanation just because it reads convincingly.

## Documentation update convention

- Every authorized delivery: commit code+tests FIRST, commit docs
  SECOND, as two separate commits.
- Record a GPT verdict (ACCEPTED or CHANGES REQUIRED) at the NEXT
  authorized update, folded into that delivery's own docs commit --
  never a standalone "record the verdict" commit by itself, unless
  explicitly asked for one.
- `decision_sheet` and `implementation_plan` both carry a revision
  number in the title and an append-only "Revision N --" note at the
  top (short, says what changed and why). Bump both together when both
  change together.
- If a prior revision's claim turns out wrong (GPT catches it),
  REPLACE the wrong text in its own section with the correct one --
  don't leave the wrong version standing "for the record." The
  top-of-file revision notes are the append-only history; the body
  sections (lettered decision records) describe current truth only.

## Delivery bundle (every round sent to GPT for review)

Build in the scratchpad directory and send as files: a
`VERIFICATION_SUMMARY.md` (what changed, why, verification discipline
applied with concrete before/after evidence, exact test counts), the
diff (`git diff <prev-commit>..<new-commit>`), the targeted test log,
the full-suite tail, AND a full repo archive at the delivered commit
(`git archive --format=tar.gz -o trading-sistem_<short-sha>.tar.gz
<commit>`) -- a diff alone forces GPT to reconstruct the current full
state of files like `decision_sheet`/`implementation_plan` by hand
from a patch; the archive is what lets them review those files (and
anything else) in their actual current form without that
reconstruction. Confirmed missing once already (Stage 5's two rounds
shipped patch+logs only, no archive -- GPT had to ask for it
separately); don't repeat that omission. Run the FULL project suite
every round -- state the exact passed/skipped count and confirm it
matches the expected delta precisely (e.g. "925 + 8 = 933," not
"roughly the same"). GPT does not have direct repository access; Radu
relays the bundle and
GPT's verdict both ways, so the bundle must be self-contained.

## Tone

Think in English, respond in Romanian. Direct, casual, no filler
("desigur," "absolut," "bună întrebare"). Short, clear, results-
focused. Push back when something doesn't add up instead of just
executing it.

## Git

Never push to a branch other than the one specified for the session
without explicit permission. Never skip a stated stop condition
("oprește-te după Stage N") to start the next stage, no matter how
ready the code looks or how small the next step seems.
