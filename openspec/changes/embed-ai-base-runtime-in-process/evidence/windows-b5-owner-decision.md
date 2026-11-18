# B5 Owner Amendment B5-r1

Status: approved on 2026-11-18. Owner: "同意B5 拆成两项证明，请继续".
This authorizes the two complementary proofs below, not a claim that they passed.
The authoritative execution state remains in the change's `tasks.md`.

## Original Conflict

The pre-amendment `embedded-ai-runtime-host` delta, scenario "Server stops while chat
streams are open", requires outputting/idle/backlogged chat-stream clients.
Original tasks 5.6 and 10.4 require the approximately 8 MiB slow-reader case and
specifically require B5 streams to use the delivered AIB chat stream.

The pinned `ai-base-runtime==0.1.1.dev4` implementation at
`_internal/http/domain_routes.py:132-152` emits small `chat.state` records when
the run status changes, plus the adapter's normal heartbeats. It does not
forward model text or tool output in that stream. The required large backlog
therefore cannot be produced faithfully from the current public chat stream
under the signed settings.

Independent read-only Validation Engineer `01a1eabb-fe7b-7e43-9649-323cca69df0d`
(`gpt-5.5`, `xhigh`) checked the spec, original tasks, current validation matrix
and runtime code. It confirmed that a controlled AppRoute stream is supplemental
transport evidence, not automatic satisfaction of the unchanged B5 clause.

## Approved Amendment

Both proofs are mandatory for `B5-stream-stop:functional`:

1. **B5-chat:** Real public AIB chat subscriptions under a deterministic local
   model validate chat termination, session/run identity and normal host
   shutdown. Preserve actual `chat.state` payloads; do not claim model-text
   streaming or manufacture a large chat response.
2. **B5-transport:** Controlled active/idle/approximately 8 MiB slow/non-reading streams through
   the same installed AIB WSGI adapter and actual `serve` validate transport
   backpressure, terminal-before-close for reading clients and resource cleanup.
   After a 3-second pause the slow reader must receive its terminal before EOF;
   a client that never reads may lose buffered output at the existing flush
   deadline. It must not prevent bounded normal stop.

Retain heartbeat 2 seconds, stream/short quotas 4/4, 14 Waitress threads,
2-second terminal grace, 3-second pause, 10-second normal shutdown, normal
exit0 and no residual owned resources. Exercise the supported native stop
triggers; an HTTP-test-server-only result is insufficient.
Do not pad chat responses, change the wheel in place, relax thresholds, use
skip/xfail, or substitute either proof for their conjunction.

## Traceability And Supersession

`B5-r1` supersedes only the requirement that the approximately 8 MiB transport
load in original tasks 5.6/10.4 must come from chat events. It does not change
the candidate, public API, timeout values, admission limits or other clauses.
The original task paragraphs, `windows-coverage.json` census and original
requirement digests remain unchanged as history. Current delta scenarios,
steps and validation matrix refer to this approved version. Final native
evidence must bind this record's hash and both proof IDs; old chat-only or
AppRoute-only evidence cannot qualify the amended clause.

## Checkpoint

The request is raised under the existing stop/escalation rule for an unavailable
mandatory Windows assertion/frozen-runtime change. It is not a new arbitrary
quality gate. No performance work or other-App expansion was started.
The owner approved the amendment and resumed implementation. Test production
and semantic evidence validation remain W2.HOST work; W2.CERTIFY and W2.R
remain open.
