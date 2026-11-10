## ADDED Requirements

### Requirement: User projects are provider-neutral durable containers
The application SHALL allow a trusted local operator to create, list, inspect and archive named projects without any predefined Chiplet project, scope, identifier or model prompt.

#### Scenario: Arbitrary projects survive reload
- **WHEN** an operator creates projects named Alpha and Beta and opens a new service instance
- **THEN** both projects SHALL retain their distinct IDs and names
- **AND** neither creation SHALL contact a tracker or model service

#### Scenario: Project ownership is checked
- **WHEN** an actor queries or changes another actor's project
- **THEN** the application SHALL return PROJECT_NOT_FOUND without leaking project details
- **AND** SHALL NOT create a stage or audit mutation for that project

### Requirement: A stage freezes one explicitly selected provider scope
Each stage SHALL contain one immutable, hash-bound scope descriptor obtained from the existing source catalog, not a caller-forged definition. Jira and HSD-ES SHALL use the same project/stage model.

#### Scenario: Jira stage requires explicit scope binding
- **WHEN** an operator selects an enabled Jira scope and its explicitly bound profile
- **THEN** the application SHALL freeze the exact query, profile ID, provider endpoint and source reference
- **AND** SHALL reject an inferred, missing, disabled or mismatching binding

#### Scenario: HSD-ES stage uses its own saved query
- **WHEN** an operator selects an enabled HSD-ES profile with a saved query reference and version evidence
- **THEN** the application SHALL freeze that saved-query definition without requiring a Jira scope ID
- **AND** no Jira-specific query SHALL be synthesized

#### Scenario: Rule changes preserve existing history
- **WHEN** the selected source query, endpoint or saved-query version changes after stage creation
- **THEN** the saved stage SHALL remain unchanged and report source_changed on inspection
- **AND** adopting the changed rule SHALL require a new stage key

#### Scenario: Source removal does not delete stage
- **WHEN** the source scope or provider profile is archived or removed
- **THEN** the project and frozen stage SHALL remain readable to their owner
- **AND** current source availability SHALL be reported without cascading deletion

### Requirement: Project commands are safe and bounded
Project commands SHALL check trusted actor ownership, project lifecycle, input shape and stage identity. They SHALL NOT accept raw credentials, arbitrary scope documents or an actor ID from command input.

#### Scenario: Stage creation is idempotent
- **WHEN** the same project, stage key and exact source descriptor are submitted twice
- **THEN** the same stage SHALL be returned without a duplicate audit mutation
- **AND** a different descriptor under that key SHALL return STAGE_RULE_IMMUTABLE

#### Scenario: Archive prevents new work but preserves inspection
- **WHEN** a project is archived
- **THEN** new stages SHALL be rejected
- **AND** existing stages SHALL remain readable and repeated archive SHALL be idempotent

#### Scenario: Local CLI invokes the same application API
- **WHEN** the operator uses project_catalog create, list, show, add-stage or archive
- **THEN** the command SHALL use the public project module API and a trusted local actor
- **AND** output SHALL be versioned JSON with safe English errors and no provider credentials

### Requirement: Provider coverage controls reports
The reporting pipeline SHALL use provider-neutral work-item identities, immutable captures and explicit per-part coverage, preserving raw evidence and independent capture, accepted-summary and publication checkpoints.

#### Scenario: HSD-ES lacks complete comment history
- **WHEN** only canonical fact fields are available from the HSD-ES provider
- **THEN** the report SHALL describe the actual coverage as partial or unsupported
- **AND** SHALL NOT claim to have read all comments or reuse a Jira completeness proof
- **AND** a summary whose profile requires complete comments or history SHALL NOT advance its accepted watermark
- **AND** any published progress view SHALL retain partial status instead of complete daily-summary status

#### Scenario: Unchanged closed work item
- **WHEN** any scoped work item, including a closed item, has no relevant change and its prior summary is valid
- **THEN** the pipeline SHALL reuse that summary without invoking AI
- **AND** unfinished actions SHALL remain visible

### Requirement: UI and AI concerns remain separate
Project UI SHALL support English and Simplified Chinese; generated business summaries and reports SHALL be English while raw source text remains unchanged. Interactive chat and authoritative summary execution SHALL use separate AI policies.

#### Scenario: Language switch is display-only
- **WHEN** the user changes UI language
- **THEN** no provider sync or AI call SHALL occur
- **AND** raw evidence and published bytes SHALL remain unchanged

#### Scenario: Report execution is explicitly requested
- **WHEN** a user only opens a project, chart or report page
- **THEN** the system SHALL NOT implicitly start collection, summary generation or report publication

### Requirement: Report templates are deterministic projections
Reports SHALL use a verified provider-neutral report snapshot and versioned
templates. HTML SHALL be the primary presentation and copy/export format, while
required Markdown and Excel capabilities remain in scope. Rendering SHALL NOT
call a model, query a provider, change a stage rule or advance an analysis checkpoint.
用户自建模板的版本、填写槽和受控数据区 SHALL 遵循同change的
[report-authoring capability](../report-authoring/spec.md)，不能以现有内置模板选择替代。
显式AI填写属于独立候选操作，不是本条的rendering。

#### Scenario: User changes report purpose or presentation
- **WHEN** an operator selects a supported daily or weekly template over the same retained snapshot
- **THEN** the output SHALL preserve source identities, original evidence, coverage, unresolved actions and source cutoff
- **AND** template identity/version/hash SHALL be recorded independently from the analysis profile
- **AND** a template requiring new inference SHALL NOT silently start a new analysis

#### Scenario: Daily history includes reopened and unchanged work
- **WHEN** retained evidence includes a closure followed by reopening or an unchanged ticket with an unfinished action
- **THEN** the report SHALL preserve the known transition sequence and outstanding action
- **AND** scope entry, issue creation, scope departure, closure and access loss SHALL remain distinguishable
- **AND** missing/partial days SHALL NOT be represented as no-change days

#### Scenario: Meeting baseline differs from accepted-summary baseline
- **WHEN** a partial standup was finalized while one work item still needed analysis
- **THEN** the next report SHALL retain that pending item's outstanding source/summary references
- **AND** model input SHALL still accumulate changes since its last successful accepted summary
- **AND** a draft copy or historical export SHALL NOT replace the default finalized standup baseline

### Requirement: HTML drafts allow attributable human editing
The application SHALL support saved report drafts with manual notes and narrative
overrides. Original source facts and accepted model content SHALL remain immutable.
Human text SHALL retain its original language and verified authorship separately
from English generated content.
Editing SHALL occur directly in rendered rich text using a WYSIWYG component.
A Markdown or plain-text textarea with a separate preview SHALL NOT satisfy
this editor requirement.

#### Scenario: Operator edits rendered rich text
- **WHEN** the operator changes an allowed narrative region or adds a formatted meeting note directly in the report
- **THEN** saving and reopening the same revision SHALL preserve the supported text and formatting
- **AND** the application SHALL validate the versioned editor payload without trusting active HTML
- **AND** source provenance, revision conflicts and explicit finalization SHALL retain their existing guarantees

#### Scenario: Operator adds a meeting note or edits narrative
- **WHEN** an authorized operator saves an edit against an exact draft revision
- **THEN** the application SHALL create a durable new local revision with original text/hash and human provenance
- **AND** generated report output SHALL identify human-authored content
- **AND** Jira facts, accepted summaries, owner confirmation and model inputs SHALL remain unchanged

#### Scenario: Concurrent editors or a changed source invalidate a write
- **WHEN** a new save uses a stale expected revision or current finalization uses a superseded source snapshot
- **THEN** the application SHALL refuse the conflict and retain existing draft revisions
- **AND** it SHALL NOT silently rebase notes, overwrite history or retry under a new command identity

### Requirement: Formatted HTML copy is independent of application UI
The report SHALL provide a static self-contained HTML document and a complete
HTML body fragment with inline presentation, plus a plain-text alternative.
Editor controls, executable content, external assets and application CSS
dependencies SHALL NOT appear in email output.

#### Scenario: Operator copies a saved report into an email draft
- **WHEN** the operator clicks Copy for the exact saved preview revision
- **THEN** the application SHALL request clipboard formats text/html and text/plain from a user gesture
- **AND** the HTML SHALL contain complete tables, text labels, safe links and notes without editor controls
- **AND** compatibility SHALL be accepted only after paste into the actual selected HTML-mode email client is verified
- **AND** copying SHALL NOT send a message, commit a report or claim delivery

#### Scenario: Clipboard permission or size prevents copying
- **WHEN** clipboard write is denied/unavailable or its configured size bound is exceeded
- **THEN** the application SHALL show failure without claiming success or silently copying plain text
- **AND** a within-limit standalone HTML download SHALL remain available
- **AND** no report data SHALL be truncated to make the copy succeed

### Requirement: Final report Git publication requires explicit confirmation
Saving or exporting a draft SHALL NOT finalize a report. An explicitly confirmed
finalization SHALL commit the exact selected revision using the existing stage
data-Git writer and return its verified commit identity. This SHALL NOT delay
the existing archival of raw captures and accepted summaries.

#### Scenario: Operator chooses whether to commit a report
- **WHEN** an operator only saves, previews, copies or downloads a draft
- **THEN** no final publication or meeting checkpoint SHALL be created
- **WHEN** the operator explicitly confirms finalization
- **THEN** original snapshot, template identity, edit history and exact final HTML/plain bytes SHALL be committed to the registered data repository
- **AND** no developer repository, credential, unrelated draft, remote configuration or push SHALL be included

#### Scenario: Finalization is repeated or interrupted
- **WHEN** the same finalization command is replayed after a failure or lost response
- **THEN** the existing intent, durably retained exact file payloads and matching commit SHALL determine the result
- **AND** finalization SHALL preserve those payloads before beginning the Git side effect, rejecting missing or corrupted bytes on recovery
- **AND** the application SHALL NOT create a second edition, rerun the model or change template/source bytes
- **AND** an uncommitted failure SHALL preserve the draft and leave publication checkpoints unchanged

#### Scenario: Published report is amended
- **WHEN** an operator changes a previously finalized report
- **THEN** the application SHALL create a linked new draft and edition rather than overwrite the original
- **AND** old downloads SHALL return their retained original bytes
- **AND** archived project read permissions SHALL NOT authorize new report writes

### Requirement: Project browser access uses verified identities and explicit confirmation
Project browser routes SHALL require a server-verified identity even when legacy dashboard pages allow
anonymous access. All browser mutations SHALL require CSRF protection and the same owner checks as the
public Project API. A stage SHALL be confirmed against the exact source definition shown in its preview.

#### Scenario: Browser credentials are absent or forged
- **WHEN** a request lacks successfully verified credentials or supplies a forged actor/header/session value
- **THEN** project routes SHALL refuse access before reading project or source data
- **AND** SHALL NOT infer local_operator from an anonymous request or the first configured account

#### Scenario: CLI and browser sharing is explicitly configured
- **WHEN** a verified username exactly matches the operator-configured local owner mapping
- **THEN** browser and CLI SHALL access the same local_operator-owned projects
- **AND** other verified usernames SHALL retain separate owner identities

#### Scenario: Source changes after browser preview
- **WHEN** the source definition changes between preview and confirmation
- **THEN** the application SHALL reject confirmation without a new stage or mutation audit
- **AND** SHALL require a new preview rather than accepting a caller-provided replacement descriptor

#### Scenario: Preview is stale or belongs to another browser identity
- **WHEN** confirmation uses a missing, modified, expired, wrong-project or wrong-owner preview
- **THEN** the application SHALL refuse the mutation
- **AND** a repeated confirmation SHALL NOT create a second stage or audit event

### Requirement: Application integration assets are versioned and isolated
The application SHALL declare report AI work as Metrics-owned task profiles in `ai_profiles` with instructions, input/output schemas and policy, requested by exact `id@version` through the project_management task-run port and checked with the runtime `check_app_package`. Strict summary and authoring profiles SHALL NOT declare tools. Optional assistant tools SHALL be read-only and SHALL NOT be required for authoritative summaries.

#### Scenario: Profile admission fails
- **WHEN** a requested profile is undeclared or disabled, has no configured model, or the input violates its schema
- **THEN** the runtime SHALL reject the run before any model request with `profile_not_declared`, `profile_disabled`, `model_not_configured` or `input_schema_invalid`
- **AND** the application SHALL NOT report AI readiness from profile file existence alone

#### Scenario: A strict profile references tools
- **WHEN** a strict summary or authoring profile definition references a tool, agent, skill or host action
- **THEN** `ai_host` package conversion and the Metrics contract tests SHALL reject it
- **AND** SHALL NOT declare a placeholder profile in its place

#### Scenario: Summary uses explicit data rather than interactive tools
- **WHEN** a report summary task executes
- **THEN** its model-visible input SHALL contain only approved previous summary, cumulative delta and required evidence
- **AND** SHALL exclude development skills, implicit chat history, tracker credentials and arbitrary tool access

#### Scenario: Optional assistant reads another project
- **WHEN** an optional assistant read tool targets a project, stage or artifact outside the authenticated principal's authority
- **THEN** the application service SHALL reject it
- **AND** instructions SHALL NOT substitute for authorization

### Requirement: AI contract upgrades have explicit migration and version admission
The application MAY adopt breaking embedded-runtime changes. Each adopted runtime version SHALL pass MDB-2 version admission and SHALL be mapped to the affected reporting consumers and their migration tests. Preserving obsolete API signatures SHALL NOT be required, while ownership, source integrity, truthful execution accounting and business approval guarantees SHALL remain enforced.

#### Scenario: AI execution is not available
- **WHEN** the runtime rejects admission, is not running (`RUN_UNAVAILABLE`) or is busy (`RUN_BUSY`)
- **THEN** no model request or business publication SHALL occur and the application SHALL surface the code with its runtime `recovery`
- **AND** SHALL NOT fall back to chat or another profile version to execute an authoritative summary
- **AND** local project and stored-history inspection SHALL remain independent of AI readiness

#### Scenario: A breaking change affects existing workbench consumers
- **WHEN** an admitted runtime version changes context, tool, approval or host-action interfaces used by the existing Dashboard
- **THEN** the migration plan SHALL name those existing consumers and their replacement tests
- **AND** SHALL NOT classify their migration as the optional new project assistant

#### Scenario: An application identity or protocol is replaced
- **WHEN** an upgrade replaces app identities, profile versions or result envelopes
- **THEN** the migration SHALL preserve traceable object ownership and approved business-result acceptance
- **AND** SHALL associate replaced protocol assertions with the new contract and negative tests
- **AND** documentation delivery alone SHALL NOT count as application migration acceptance

### Requirement: Installed AI runtime qualification is isolated from product execution
The project SHALL qualify the pinned `ai-base-runtime` wheel by its recorded digest, using the runtime testkit scripted model in an application-owned isolated environment, before production integration. Development qualification SHALL NOT read deployment credentials, access business data or claim real-model qualification from synthetic tests.

#### Scenario: Runtime artifact identity is missing or wrong
- **WHEN** the pinned runtime wheel is unavailable or its digest differs from the admitted record
- **THEN** qualification SHALL fail before any model request
- **AND** SHALL NOT import another repository's source or site-packages as an installation fallback

#### Scenario: Synthetic runtime checks succeed
- **WHEN** host conformance and reporting port tests pass with the scripted model
- **THEN** the evidence SHALL identify the runtime version, wheel digest, environment, selected cases and actual results
- **AND** SHALL NOT mark real model execution, cancellation, recovery or application result acceptance as passed without their own tests

### Requirement: Runtime results do not replace application authority
The task-run port SHALL preserve original-key recovery, and a wait timeout SHALL NOT be treated as cancellation. A completed runtime run SHALL NOT imply domain acceptance, saved human edits or publication. Each report AI use SHALL request its own declared profile version and SHALL NOT borrow another profile's permission.

#### Scenario: Run outcome is unknown
- **WHEN** a task-run outcome is unknown after a timeout, `RUN_UNAVAILABLE` or a process restart
- **THEN** the application SHALL resolve it with the original `client_run_key` and its stored run record
- **AND** SHALL NOT issue a new key or renew the original deadline to manufacture success

#### Scenario: A schema-valid result is semantically invalid
- **WHEN** a completed run output matches its profile output schema but contains an ungrounded owner, invalid source evidence or a mismatched application binding
- **THEN** the application SHALL refuse domain acceptance
- **AND** SHALL preserve source, accepted-summary and publication watermarks

#### Scenario: Authoring profile is not available
- **WHEN** an AI filling request finds no declared and enabled `metrics.report_authoring` profile version
- **THEN** the application SHALL report `REPORT_AI_UNAVAILABLE` and preserve manual editing
- **AND** SHALL NOT reuse the summary profile as an authoring permission

#### Scenario: Final authoring qualification crosses a work week
- **WHEN** the full-week authoring qualification is executed
- **THEN** it SHALL run the accepted five-day and next-week scenario through actual application, editor and storage paths
- **AND** SHALL preserve human text, deletions, colors, original source statuses, row identity and unresolved actions
- **AND** SHALL keep real-provider, model, Outlook and scheduling qualification separate from synthetic success

### Requirement: Provider access shares one public authority
The Provider CLI, project reporting worker and affected legacy sync consumers SHALL use the same approved connection resolution and provider access service. Jira and HSD-ES SHALL retain their adapter-specific authentication and coverage semantics.

#### Scenario: Metadata and stored capture queries are offline
- **WHEN** an operator requests provider status or an existing captured item without explicit online execution
- **THEN** the command SHALL not contact the provider or model
- **AND** SHALL report the actual captured coverage without initiating a new capture

#### Scenario: Public capture is not yet runtime-qualified
- **WHEN** provider_access capture or operation is invoked before W7 runtime capability is installed and qualified
- **THEN** it SHALL return CAPABILITY_UNAVAILABLE with no operation ID, capture write or upstream call

#### Scenario: Endpoint and credential selection disagree
- **WHEN** a profile endpoint differs from the endpoint bound to its selected credential source
- **THEN** access SHALL be rejected before transmitting credentials
- **AND** an authentication failure SHALL NOT cause fallback to another token or browser cookie

#### Scenario: Legacy sync delegates without redefining scope
- **WHEN** legacy sync and the new Provider CLI use the same explicit profile and approved scope
- **THEN** they SHALL resolve the same approved connection identity and compatible source facts
- **AND** project-stage access SHALL not silently choose the first enabled scope or an arbitrary query

### Requirement: Credential adoption is explicit and non-destructive
The application SHALL prefer the selected Dashboard credential source and MAY adopt an explicitly selected legacy PAT through a trusted local, previewable, protected migration operation.

#### Scenario: Adoption is previewed
- **WHEN** the operator previews adoption without apply
- **THEN** no credential or profile reference SHALL change
- **AND** output SHALL exclude the token, token hash, credential contents and raw private file path
- **AND** the local input path SHALL NOT propagate into profile, audit, operation logs, browser state or model input

#### Scenario: Destination exists or update fails
- **WHEN** a target credential already exists without explicit replacement confirmation, or writing the new protected secret fails
- **THEN** the prior source and destination references SHALL remain intact
- **AND** no success or secret exposure SHALL occur

### Requirement: Reuse preserves semantics and source evidence
Each donor capability migration SHALL identify its fixed source revision, dependency/resource closure, destination consumers, source-to-target tests and retained limitations. Source presence or historical tests SHALL NOT substitute for target-environment verification.

#### Scenario: Donor code assumes Jira-only identifiers
- **WHEN** report links, spreadsheet identifiers or evidence fields are reused for HSD-ES
- **THEN** provider-specific validation SHALL replace Jira-only assumptions at the adapter boundary
- **AND** existing evidence, permissions and lossless rendering guarantees SHALL remain enforced

#### Scenario: Planned donor functionality is not implemented
- **WHEN** a donor capability such as external dependency capture or attachment body collection has no completed implementation
- **THEN** the migration plan SHALL list it as new implementation work
- **AND** SHALL NOT count it as transferred or remove its required acceptance scenarios
