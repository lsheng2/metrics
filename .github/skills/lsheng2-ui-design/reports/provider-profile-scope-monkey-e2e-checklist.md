# Provider/Profile/Scope Monkey-User E2E Checklist

Purpose: verify that a non-expert operator can create a provider profile, create a scope, bind them, and understand which provider metadata feeds dashboard elements.

## Entry And First Decision

- Open `/provider-setup/`.
- Click `New Profile`.
- Verify the editor opens as a blank profile rather than cloning an existing profile.
- Verify Jira, HSD-ES, and reserved GitHub choices are presented as provider cards/tabs.
- Verify selected provider has the circular green check marker.
- Verify Jira uses green identity color, HSD-ES uses blue, and GitHub uses purple when shown.

## Jira Profile Path

- Choose Jira.
- Leave required fields blank and click `Test Connection`.
- Verify the required summary appears and missing fields receive field-level highlight/invalid state.
- Fill profile id, display name, base URL, email or username, auth option, and token.
- Verify token displays as `********` after save while non-secret values remain readable.
- Click `Test Connection`.
- Verify success/failure feedback is visible near the editor and does not expose the token.
- Save draft, enable, then return to inventory and verify the profile row is visible.

## HSD-ES Profile Path

- Choose HSD-ES.
- Verify auth options are separated so token login and username/password login do not look like one mixed credential set.
- Fill profile id, display name, base URL, saved query id, tenant, subject, auth option, and required credential fields.
- Click `Test Connection`.
- Verify the test reads saved-query id, tenant, and subject from the visible profile fields.
- Verify success/failure feedback is visible and does not expose password or bearer token.
- Save draft or enable and verify inventory status updates.

## Scope Binding Path

- Open `/bug-trend/scope-config/?mode=new`.
- Verify provider selection is the first major decision and uses the same provider card/tab style as Provider Setup.
- Choose Jira or HSD-ES.
- Verify profile selection is limited to the selected provider.
- Fill scope name and required query/metadata fields for the selected provider.
- Click save/enable with missing required fields and verify the same required-field highlight behavior as Provider Setup.
- Modify a field and verify dirty/unsaved markers appear plus Save and Cancel choices remain aligned.
- Save the scope, return to `/bug-trend/scopes/`, and verify the scope shows its explicit profile/provider binding.

## Metadata To Dashboard Mapping

- Open Bug Trend dashboard for the new scope.
- Verify profile-level onboarding data explains how provider metadata is found.
- Verify scope-level fields explain which metadata becomes chart series, filters, evidence table fields, owner/component columns, and export data.
- Verify refresh/test actions show whether metadata came from Jira, HSD-ES, or fixture data.

## Import / Export / Archive / Delete

- Export a profile and verify secrets are redacted.
- Import a profile and verify required-field validation still applies before enable/test.
- Archive a profile and verify bound scopes show a clear unavailable or repair state.
- Delete a profile only through the exact confirmation path.
- Export a scope and verify binding references are present without secrets.
- Archive/delete a scope and verify the inventory row and dashboard route do not silently reuse stale metadata.

## UI Gate Evidence

- Run `scripts\validate_ui_design_gate.ps1 -Broad`.
- With a local server running, run `scripts\validate_ui_full_manifest_gate.ps1 -BaseUrl http://127.0.0.1:8000 -NoScreenshots`.
- Refresh `.github/skills/lsheng2-ui-design/reports/ui-gate-report.md` before scoped commit/push.
