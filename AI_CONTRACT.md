# Dashboard AI Development Contract

Effective: 2026-11-05, following the user's approved delivery reassessment.
This is the single repository-level development contract for Codex, Copilot and Claude.
It does not grant permissions beyond the current user request or higher-level instructions.

## 1. Read And Execute One Plan

- Read this contract, the current task frontier, and the relevant module/specification before work.
  Use [README](README.md) and the current guides for product context; load detailed history only
  when it answers a concrete question. Do not repeatedly reload unchanged historical reports.
- OpenSpec owns requirements and changes; Superpowers supplies implementation and quality methods.
  One change has one authoritative `tasks.md`, one implementation coordinator and one evidence trail.
- The current reporting ledger is
  [provider-neutral reporting tasks](openspec/changes/add-provider-neutral-project-reporting/tasks.md).
  Skill-default plan/ledger locations must not create a second execution state.
- Reuse approved decisions. Before a coding packet identify its user outcome, producer/consumers,
  exact interface, owned files, environment, negative checks, expected cost and stopping condition.
- Separate implementation, validation, external qualification and publication. An unchecked parent
  summary is not an instruction to reimplement its completed children.
- User pauses stop product execution after safe owned cleanup. Analysis or documentation requests
  do not resume implementation; a later explicit resume does. Read the newest request at handoff.

## 2. Preserve The Product Boundaries

- Dashboard is a modular monolith. Modules communicate through public `app/api/` boundaries.
  Domain logic stays framework-free; structured values use `@dataclass(slots=True)`.
- `project_management` owns projects/stages, accepted summaries, report editing and publication;
  `provider_sync` and provider adapters own external access. Chiplet is an instance, not a default.
- Reuse existing libraries and module APIs. Keep provider-specific authentication, IDs, queries and
  pagination in adapters. Do not invent a parallel product module for each provider.
- Use semantic HTML, Bulma and htmx. Chart.js supports charts; the approved locally bundled
  Milkdown/ProseMirror adapter supports report editing. This editor is an explicit JS-library
  exception, not permission to replace the application with a new frontend framework.
- Keep source, accepted-analysis and editorial baselines separate. Save is not Finalize.
  Only verified data-Git finalization advances the editorial baseline; weekly views do not.
- Canonical rich-text fragments preserve human text, deletion, paint, links and provenance.
  Markdown/plain/HTML are projections, not an excuse to round-trip away unsupported formatting.
- Ticket status comes from the captured provider record, never the model. Current assignee,
  explicit action owner and suggested owner remain distinct. Preserve one ticket per stable row.
- UI supports English and Simplified Chinese. Canonical generated business output is English;
  raw evidence and proper names retain their original text.
- Keep comments focused on non-obvious invariants, compatibility or security constraints.
  Prefer clear code; see [comment policy](.github/ai-governance/code-comment-policy.md).

## 3. Development And Runtime AI Are Different

- Runtime AI receives only its versioned task profile, bounded explicit input and output schema.
  It must not load development instructions, planning skills or repository-wide authority.
- AI Base owns execution facts and public SDK/API contracts. Dashboard owns source eligibility,
  evidence validation, candidate acceptance, human acceptance and report publication.
- Reuse the installed SDK. Do not build a second SDK journal, process manager or persistent task engine.
  Summary and authoring have separate business profiles and acceptance rules.
- Persist the exact request/key/store/profile/deadline before dispatch. Unknown submit is observed
  by its original key; it is not permission for another POST, new deadline or refunded budget.
- Schema/hash validity is not business acceptance. AI Apply only changes local dirty content;
  Save verifies the server-owned candidate receipt under the existing revision/CAS boundary.
- Changes to SDK/profile/pack/runtime compatibility require explicit selection and consumer checks.
  Never patch immutable released artifacts, old request bytes or historical receipts in place.

## 4. Match Tests To The Risk

- Use TDD for behavior changes: reproduce a meaningful failure, make the smallest correct change,
  then run direct and affected-consumer checks. Adding missing proof of existing behavior need not
  manufacture a product failure or change already-correct code.
- Test observable business contracts. One test may use several assertions for one user story or
  invariant. Mock external/SPI boundaries, not the business logic being qualified.
- HTTP/CSRF/owner validation, template coverage, schema/nullable values, dependency wiring and
  mounted editor behavior are required where they carry a contract. There is no blanket ban on
  testing views, templates, containers or validation rules.
- Reporting uses its existing L0 pure, L1 storage/service, L2 HTTP, L3 mounted-browser and L4 joined
  layers. Each layer answers a different question; pure field tests must not require a full Git,
  database, browser or Base fixture. Mutable state remains isolated between scenarios.
- Use explicit test paths: default pytest discovery does not cover all modules, including
  `project_management` and `provider_sync`. Collection, empty selections and skips are not acceptance.
- For reporting, use the selected SDK environment and no-dotenv entry in
  [development and validation](docs/development/reporting-delivery.md). Do not accidentally run
  migrated consumers in the retained legacy `.venv` or test against the existing 8017 service.
- Inspect the actual HTTP result/state before waiting for navigation. Preserve failed responses,
  screenshots and logs under unique names. A later pass does not explain an earlier failure.
- Before review/commit, run the scoped size/whitespace gates and inspect staged bytes and paths.
  Django integration changes also require isolated `check` or its recorded equivalent.

## 5. Control Execution Cost

- Deliver a small complete user workflow before expanding another subsystem. A completed packet
  should produce a scoped commit or an explicit reason it cannot yet be published.
- Review implementation, evidence and the next dependency boundary together when appropriate.
  Re-review only the changed findings/consumers; missing expected evidence is readiness, not
  automatically a newly discovered product defect.
- One production writer per repository. Use another agent only for a distinct independent task
  or gate. Codex subagents explicitly use `gpt-5.5` with `xhigh`; do not alter the main model.
- After two equivalent failures without new information, change the hypothesis or instrumentation.
  Do not blindly retry, weaken checks, extend an existing operation deadline or invent progress.
- Record setup, call and cleanup separately when measuring cost. Do not add overlapping timers,
  equate pytest/JUnit duration with whole-turn wall time, or promise unmeasured savings.
- At each packet boundary and after 60 minutes on the same question, decide continue, narrow the
  experiment or return to local design. Do not disguise new architectural scope as endless cleanup.
- Bind evidence to runtime code, test/fixture inputs and environment. Reuse unaffected evidence
  with an explicit dependency rationale; changed shared fixtures may invalidate consumers.

## 6. Safety And Source Authority

- Preserve pre-existing work verbatim unless this request explicitly owns the change. Stage an
  allowlist, never the whole dirty tree; verify the remote SHA after an authorized push.
- Development data is isolated from user data. Do not load real credentials, call real providers
  or models, migrate production databases, activate scheduling or send reports without authorization.
- Code-origin push permission is not data-Git export permission. Data remotes, backup destinations
  and formal activation keep their separate approval boundaries.
- Source reading is not provider writing. Recheck owner/scope/principal at the relevant boundary;
  do not use old cache membership or a same-host match as permission.
- Never guess Jira/HSD-ES endpoint, auth, paging or field semantics. Consult the authoritative
  [provider source references](docs/development/provider-source-authority.md) when changing them.
- Do not log or commit credentials, cookies, authorization headers or enterprise runtime content.
  Synthetic credentials must be clearly synthetic and restricted to owned test fixtures.
- No disk-free-space admission checks. Application quotas, path/ownership checks and actual I/O
  failure handling remain required; failed writes must not advance successful watermarks.
- Declare process ownership, command bounds, evidence and cleanup before long runs. Stop only
  owned resources; normal exit and emergency cleanup are separate conclusions.
- Keep one current guide and explicit supersession links. Historic documents and external donor
  instructions are evidence, not competing authority. No global skill/hook/config changes by default.
