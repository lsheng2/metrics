## ADDED Requirements

### Requirement: Dashboard admits an explicit SDK and contract pack combination
Dashboard SHALL admit Python SDK `0.2.0a1` with task-run/1 and the unchanged trusted `0.1.0a2`
contract pack. Dependency selection and runtime compatibility checks SHALL agree.
The application SHALL retain profile, schema, source, owner, evidence and business-CAS validation.

#### Scenario: Delivered SDK loads the original trusted pack
- **WHEN** the installed SDK is the selected `0.2.0a1` and the original pack content is intact
- **THEN** the application SHALL load its summary contract and validate the original profile
- **AND** SHALL NOT rewrite the pack, accepted history, Run keys or execution qualification

#### Scenario: Unsupported or corrupted combination is supplied
- **WHEN** the SDK version, manifest digest or a listed profile/schema file differs from the selected combination
- **THEN** the application SHALL return `ANALYSIS_CONTRACT_INVALID`
- **AND** SHALL NOT submit a Run, disable the check or fall back to another version/profile

### Requirement: Pre-integration qualification stops before a joined service run
The user-requested pre-integration phase SHALL end at `IP-SDK020-READY`.
It SHALL use a separately installed SDK and the actual application consumer with controlled
transport. It SHALL NOT start Base HTTP, change the main environment or control an unrelated service.

#### Scenario: Pre-integration proof succeeds
- **WHEN** nonempty selected consumer tests pass with exact package/pack identity and no application network attempts
- **THEN** the coordinator SHALL preserve a source-bound readiness receipt
- **AND** Windows standard-library socketpair IPC SHALL be scoped and counted separately without allowing arbitrary loopback connections
- **AND** SHALL stop before joined integration until the user explicitly releases the integration point

#### Scenario: Qualification fails or imports the wrong SDK
- **WHEN** the selected target is wrong, a package byte differs, an application network attempt occurs, or a test fails
- **THEN** the result SHALL remain failed/not-ready with the actual evidence
- **AND** SHALL NOT be relabeled as an integrated or deployed application

### Requirement: SDK convenience behavior does not replace application authority
The SDK and application SHALL preserve original-key recovery and distinct wait/cancel semantics.
SDK result integrity SHALL NOT imply domain acceptance, saved human edits or publication.

#### Scenario: Submit response is lost
- **WHEN** a submitted request outcome is unknown
- **THEN** the application SHALL query the original clientRunKey and store
- **AND** SHALL NOT issue a new POST/key or renew the original deadline to manufacture success

#### Scenario: A structurally valid result is semantically invalid
- **WHEN** a valid SDK envelope contains an ungrounded owner, invalid source evidence or mismatched application binding
- **THEN** the application SHALL refuse domain acceptance
- **AND** SHALL preserve source, accepted-summary and publication watermarks

### Requirement: Subsequent integration has explicit reachable dependency gates
Base and Dashboard SHALL develop within their own ownership boundaries and join only the
capabilities needed by the selected packet. SDK020.JOIN, DAILY, ASSIST and the full-week JOIN
SHALL have explicit inputs, APIs, refusal cases, evidence and replan boundaries.

#### Scenario: Optional Base capabilities remain deferred
- **WHEN** generic schema loader, durable events or standalone TestKit are not delivered
- **THEN** the selected migration SHALL use existing public SDK/pack and qualified synthetic fixture boundaries
- **AND** SHALL NOT wait for unrelated capabilities or fabricate them in Dashboard

#### Scenario: Authoring profile has not been qualified
- **WHEN** an AI filling request lacks its own authoring profile/registration/grant evidence
- **THEN** the application SHALL report `REPORT_AI_UNAVAILABLE` and preserve manual editing
- **AND** SHALL NOT reuse the summary profile as an authoring permission

#### Scenario: Final authoring qualification crosses a work week
- **WHEN** the authorized post-integration phase reaches the full-week JOIN
- **THEN** it SHALL execute the accepted five-day and next-week scenario through actual application/editor/storage paths
- **AND** SHALL preserve human text, deletions, colors, original source statuses, row identity and unresolved actions
- **AND** SHALL keep real-provider/model/Outlook/scheduling qualification separate from synthetic success
