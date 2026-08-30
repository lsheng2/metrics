# Jira Onboard Page for Django Web

| Field | Value |
| --- | --- |
| `id` | `BLG-20260824-jira-onboard-page` |
| `title` | Jira Onboard Page for Django Web |
| `status` | `accepted` |
| `source` | User request on 2026-08-24 with attached Jira credentials dialog reference image. |
| `problem` | New users currently need to understand provider connection settings, credentials, and scope setup from scattered configuration surfaces instead of a guided web onboarding flow. Jira is the first required provider, but future providers such as GitHub should not require a separate onboarding architecture. |
| `user_value` | A dashboard operator can connect or verify a work-tracker provider from the Django web UI, understand what information is required, and proceed toward scope configuration without editing environment variables first. |
| `owner_paths` | `ui_web/`, `jira_sync/`, `bug_metrics/`, `metrics/settings/`, `openspec/docs/current-baseline/bug-trend-scope-config-micro-architecture.zh.md` |
| `authority` | Provider connection configuration, secret-handling rules, provider metadata discovery boundary, `jira_scope_config` as the current saved Jira scope semantic authority. |
| `risk` | `medium`: onboarding touches credentials and provider connectivity, so a careless UI could leak secrets, duplicate config truth, bake Jira-only assumptions into reusable flow, or imply live dashboard readiness before durable sync is configured. |
| `trigger_to_start` | User asks to implement Jira onboarding, or a deployment needs non-developer users to configure Jira access and create their first Bug Trend scope from the web UI. |
| `non_goals` | Do not implement this as part of backlog capture. Do not store raw passwords in application tables. Do not replace `JiraScopeConfig` or move project-specific Jira semantics into global environment variables. Do not live-query Jira on every dashboard render. |
| `dependencies` | Decide the allowed secret-storage mechanism for provider tokens/passwords; confirm whether onboarding owns only connection verification or also first-scope creation; preserve existing M0 Intel Jira PAT connectivity and M1 durable history boundaries; define the provider-neutral connection profile contract before adding GitHub or another provider. |
| `validation_gates` | Focused tests for form parsing and credential redaction; `python manage.py check`; UI smoke test for connect/test/save flows without exposing secrets; architecture/security review for credential storage and provider boundary. |
| `review_gate` | Architecture and security review required before implementation. |
| `last_reviewed` | 2026-08-24: captured as deferred feature request from reference UI screenshot; accepted for backlog, not ready for implementation. |

## Deferred With Trigger

This item is intentionally not implementation-ready. Promote it to `ready-for-plan` only when the trigger occurs and the implementation owner can name the credential storage model, the provider-neutral connection-test contract, the Jira adapter fields, and the handoff boundary between onboarding and Bug Trend scope configuration.

## Product Intent

Add a Django web onboarding page that helps a dashboard operator connect a work-tracker provider and prepare the first Bug Trend scope. Jira is the first provider to implement. The attached reference image shows the necessary elements from an existing Jira client dialog, but the Metrics implementation should use its own web-first UI/UX and keep the reusable onboarding flow separate from Jira-specific server and credential details.

The page should guide the user through a small number of clear steps:

1. Choose a provider and create or select a connection profile.
2. Enter provider-specific endpoint details and verify that the service is reachable.
3. Provide credentials through an approved secret-handling path.
4. Test the connection with the same backend provider client path used by sync/discovery.
5. Continue into metadata-assisted scope configuration when the connection is healthy.

## Required UX Elements

The reference image implies these functional elements should be covered for the Jira first version, though the final layout should fit the existing Django/Bulma dashboard style and keep generic provider flow separate from Jira-specific fields:

| Element | UX expectation |
| --- | --- |
| Provider selector | Start with Jira, but model the page as provider selection plus provider-specific setup so GitHub or another tracker can be added later. |
| Instance list | Let users select an existing connection profile and create a new one without leaving the page. |
| Service endpoint | For Jira, this is the Jira server URL. Future providers may use an organization URL, GitHub host, enterprise base URL, or workspace identifier. |
| Server check result | Show a clear state such as unchecked, checking, reachable provider, unsupported provider/server type, or failed. |
| Credentials | Support provider-specific credential modes through a common secret-entry component. Jira may use username plus password/PAT; GitHub may use token/app credentials later. |
| Token guidance | Provide provider-specific help links or inline hints for creating tokens without exposing secret values. |
| Save secret choice | If supported, make persistence explicit and explain the storage boundary; default should favor least surprise and no accidental secret logging. |
| Test action | Run a bounded server-side credential test and report success/failure without printing tokens, passwords, or raw auth headers. |
| Save action | Persist only approved non-secret config plus secret references, not raw sensitive values unless an approved secret backend owns them. |
| Done/continue action | Route the user to the next setup step, likely Bug Trend Scope Config or Scope Library, only after the connection state is understandable. |

## Generic vs Jira-Specific Boundary

The implementation should be named and shaped as provider onboarding with a Jira provider adapter, even if the first route and page title use Jira language. Do not let the reusable flow depend on JQL, Jira Server/Data Center, Jira field IDs, or PAT terminology.

| Concern | Generic onboarding core | Jira-specific adapter |
| --- | --- | --- |
| Provider identity | `provider`, profile name, enabled/draft state, last checked state. | Provider value `jira`, display label such as Jira or Intel Jira. |
| Endpoint configuration | A provider endpoint model with label, value, validation state, and reachability result. | Jira server URL, Server/Data Center detection, Jira REST capability checks. |
| Credential entry | Credential mode selection, secret reference handling, redaction, persistence policy, and test result display. | Username plus password or Personal Access Token, Jira PAT help URL, Jira auth mode mapping. |
| Connection test contract | `check_endpoint(profile)` and `test_credentials(profile, secret_ref_or_draft_secret)` returning provider-neutral health/status messages. | Calls the Jira client path used by `jira_sync` and metadata discovery; maps Jira failures into neutral statuses. |
| Metadata handoff | Emits a verified connection profile reference for the scope configuration flow. | Supplies Jira projects, issue types, statuses, resolutions, fields, and field values through the Jira metadata adapter. |
| Scope semantics | Keeps scope identity, query/filter expression, lifecycle mapping, field mapping, and chart grouping outside the onboarding core. | Current persistence still lands in `JiraScopeConfig` until a future provider-neutral scope model is introduced. |
| UI copy | Prefer provider-neutral labels such as provider, connection profile, service endpoint, token, test connection, continue to scope setup. | Show Jira-specific hints inside adapter-owned sections, such as Jira server URL, Jira Server/Data Center, JQL, issue type, and PAT guidance. |
| Future GitHub fit | Reuses the same profile list, endpoint check, credential test, secret handling, status display, and next-step routing. | Adds a GitHub adapter with host/org/repo settings, token or GitHub App credentials, GitHub issue/label/milestone metadata. |

Suggested interface shape for planning, not an implementation commitment:

```python
@dataclass(slots=True)
class ProviderConnectionProfile:
    id: str
    provider: str
    display_name: str
    endpoint: str
    credential_mode: str
    secret_reference: str
    enabled: bool


@dataclass(slots=True)
class ProviderConnectionCheckResult:
    status: str
    provider: str
    display_message: str
    capabilities: list[str]
    warnings: list[str]


class ProviderOnboardingAdapter:
    provider_name: str

    def check_endpoint(self, profile: ProviderConnectionProfile) -> ProviderConnectionCheckResult:
        ...

    def test_credentials(self, profile: ProviderConnectionProfile, secret_reference: str) -> ProviderConnectionCheckResult:
        ...
```

This contract should stay focused on connection readiness. It must not absorb provider-specific scope semantics; those remain in scope config and metadata discovery.

## Suggested Web UI Direction

Use a guided setup page rather than a dense dialog clone. A practical first version could be a full-width Bulma page with a left-side connection profile list and a main setup panel containing step cards:

1. `Provider` card: provider selector, profile name, and provider-owned endpoint fields. First implementation may expose only Jira.
2. `Verify Endpoint` card: check button, detected provider/server type, capability warnings.
3. `Credentials` card: provider-owned credential mode, secret persistence notice, test button.
4. `Next Step` card: continue to metadata discovery / scope config when the connection is verified.

Prefer htmx partials for server check and credential test responses, consistent with the current `ui_web` pattern. Avoid custom JavaScript unless a browser-native or htmx interaction cannot cover the behavior.

## Architecture Notes

- The onboarding page should call a narrow provider onboarding API/facade rather than constructing provider clients directly in the template or view.
- Secret values must never be echoed into HTML after submission, written to logs, committed docs, or included in validation output.
- Connection profile identity and provider scope semantics are separate concerns. Onboarding may create or select a connection profile, but `JiraScopeConfig` remains the current authority for Jira-specific bug type, status, severity, component, owner, milestone, and bucket semantics.
- Metadata discovery can be a follow-on step after connection verification; it should reuse the provider adapter shape described in [bug-trend-scope-config-micro-architecture.zh.md](../current-baseline/bug-trend-scope-config-micro-architecture.zh.md).
- The dashboard render path must continue to read durable local history and calculation artifacts, not query Jira live because onboarding succeeded.
- GitHub or another future provider should add an adapter and provider-specific fields, not fork the onboarding flow or duplicate credential redaction logic.

## Open Questions Before Planning

| Question | Why it matters |
| --- | --- |
| Where are saved provider credentials allowed to live? | Determines whether implementation needs OS credential manager, encrypted DB storage, deployment secrets, or no web persistence. |
| What is the minimum generic `ProviderConnectionProfile` data model? | Prevents Jira URL/PAT assumptions from becoming the model that GitHub later has to distort. |
| Is the first Jira adapter only for Intel Jira, or for any Jira Server/Data Center instance? | Affects server detection copy, validation rules, and default settings. |
| Should a saved instance profile be shared across users or per Django user/session? | Affects data model, permissions, and audit expectations. |
| Does onboarding create the first `JiraScopeConfig`, or only route to the existing Scope Config page? | Prevents connection setup and scope semantics from becoming one tangled form. |
| What is the minimum acceptable credential test per provider? | Avoids over-broad provider API calls during setup and keeps failure messages bounded. |