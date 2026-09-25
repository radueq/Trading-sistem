# Spec #004 v1.0 -- Agent Interface

How a human or an AI agent (GPT, Claude, or a future model) actually
interacts with #004, and exactly where the boundary against the
deterministic core sits (Spec #004 SS35-50/SS88-94/SS110-G).

## The boundary, concretely

```
Evaluation EvidenceProfile(s)  (Spec #003, already computed)
        |
        v
evidence/packet.py: build_evidence_packet()   <- deterministic, in-core
        |
        v
EvidencePacket   (compact, flat, ~1-3KB target -- SS40)
        |
        v
   [ hand it to a human, or paste it into a GPT/Claude chat --
     exactly how this project's own spec reviews have worked so far ]
        |
        v
HypothesisProposal, as a plain dict/JSON  (produced OUTSIDE this package)
        |
        v
proposals/normalize.py: normalize_proposal()   <- deterministic, in-core
        |
        v
proposals/validator.py: validate_proposal()    <- deterministic, in-core
```

**No module under `src/hypothesis/` calls an LLM API.** TEST 39 enforces
this by AST-scanning every file for `anthropic`/`openai`/
`google.generativeai`/`cohere`/`langchain` imports, and confirms no
`agents/` adapter package exists. This is intentional per SS93-94 and
Radu's SS110-G confirmation -- building an LLM adapter before knowing the
proposal schema actually works would be automating an expensive step
with no evidence it's needed yet.

## What crosses the boundary, and in which direction

| Direction | Payload | Format |
|---|---|---|
| core -> agent | `EvidencePacket` | Python dataclass, trivially `dataclasses.asdict()`-able to JSON for pasting into a prompt |
| agent -> core | raw proposal | plain dict/JSON matching `HypothesisProposal`'s field names (`proposals/normalize.py` documents every required/optional key) |
| agent -> core | `AgentReview` | `{agent_id, model_id, hypothesis_proposal_id, stance, objections[], suggested_changes[], timestamp}` |
| human -> core | `human_decision` | a plain string, passed to `consensus/consensus.py:compute_consensus()` |

`model_id` on `AgentReview` may be a real model identifier (e.g.
`claude-opus-5-5`) or a manual-relay marker (e.g. `"manual-relay:gpt"`,
used throughout this project's own spec-review process) -- the core
treats both identically; it never branches on which model produced a
review.

## Roles (SS41-43) -- conceptual, not separate runtime agents

Spec #004 SS41 sketches three conceptual review roles (trend/market-
structure interpretation, statistical skeptic, risk/exit critique).
Nothing in `src/hypothesis/` enforces or even represents these roles as
distinct types -- `AgentReview.agent_id` is a free-form string, and a
human orchestrating the review process (today: Radu, relaying between
GPT and Claude) decides how many distinct "agents" actually review a
proposal and what each focuses on. `compute_consensus()` only cares about
the resulting `stance`s, never about which conceptual role produced them.

## Consensus never self-approves

`consensus/consensus.py:compute_consensus()` classifies the SHAPE of the
reviews that occurred (`CONSENSUS`/`DISAGREEMENT`/`BLOCKED`) purely
descriptively. `can_preregister()` is the ONE function that gates the
lifecycle, and it checks exactly one thing: whether `human_decision` is a
non-empty string. A `BLOCKED` consensus (every review objecting) does
NOT structurally prevent preregistration if a human explicitly decides
to override it -- Radu remains final approver (SS46), and this
implementation takes that literally: the human's authority is not
itself gated by the agents' agreement.

## Facts vs. interpretation (SS49-50)

Every `HypothesisProposal` carries `facts_from_evidence` (a tuple of
plain statements, meant to be literal/checkable against the
`EvidencePacket`) and `interpretation` (a single free-text string, the
agent's narrative reasoning) as two SEPARATE, both-required fields
(TEST 33). An agent's prompt should always be asked to produce both,
and a reviewer (human or agent) should read `interpretation` as a
claim to weigh, never as a demonstrated fact.

## Token economy (SS38-40)

`EvidencePacket` is deliberately flat (no nested `EvidenceProfile`/
`ConfidenceInterval` objects re-embedded) so that serializing it to JSON
or a short structured-text block for a prompt stays small regardless of
how much internal detail Spec #003's own objects carry. `decay_curve` is
the one field whose size scales with the number of horizons tested
(typically 5) -- still a handful of numbers, not a raw series.

## What a future automated adapter would need to add

If/when GPT/Claude API calls are automated (explicitly NOT built in this
spec, SS93-94), the adapter would live entirely OUTSIDE `src/hypothesis/`
(e.g. a sibling `agents/` package the core never imports), responsible
for: turning an `EvidencePacket` into a prompt, calling the model,
parsing its response into the exact dict shape `normalize_proposal()`
expects, and handling retries/rate limits/model-specific quirks. None of
that logic belongs in, or should leak into, the deterministic core --
the core's contract is the dict shape, not the model that produced it.
