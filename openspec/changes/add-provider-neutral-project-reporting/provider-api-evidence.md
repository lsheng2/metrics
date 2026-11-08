# Provider API Evidence For Capture

Checked2026-11-02. Documentation read only; no business tickets, writes or credential adoption.
This evidence informs W3.GATEWAY/CAPTURE/HSD. It is not live capability qualification.

## Jira Data Center

Authority: Atlassian versioned OpenAPI at
`https://developer.atlassian.com/server/jira/platform/jira_software_dc_10003_swagger.v3.json`.
Downloaded schema identifies10.3.26; the earlier donor probe observed deployed10.3.8.
Local exact bytes `.tmp/project-reporting-w3/jira-10-3-openapi.json`,
SHA256 `c81cfed0b29478254ec342687eccae6e26ea7df591571d763ded9e9c90aa5e1b`.
The documentation snapshot is not a claim the deployed patch version changed.

| Need | Documented boundary | Capture consequence |
| --- | --- | --- |
| Identity | GET `/rest/api/2/myself` | Verify actual principal, never infer from UI account |
| Scope | GET/POST `/rest/api/2/search`; JQL, fields, startAt, maxResults, validateQuery | Stable bounded membership enumeration; no first-N complete claim |
| Fields | GET `/rest/api/2/issue/{issueIdOrKey}`; fields/expand | Use stable ID, preserve original updated representation/raw fields |
| Comments | GET issue/comment; startAt/maxResults/orderBy | Retrieve all current pages when needed; local delta avoids sending old comments to model |
| Saved filter ID | Checked10.3 OpenAPI `FilterBean.id` is a string | Match the exact requested ID; do not coerce integer, float or boolean values |
| Changelog | Expanded issue response; no independent issue/changelog path in checked schema | Unknown/partial expansion remains a coverage gap; do not invent endpoint |

Donor read-only delta evidence is `D:/AIGC/chiplet_programmgr/docs/research/2026-10-22-jira-delta-feasibility.md`.
That is the historical source identifier. After retirement, read the same relative
path under the private archive's `snapshot`, using the
[relocation guide](../../../docs/migration/legacy-workspace-retirement.md).
Repeated comment additions have distinct IDs; all captured versions remain archived.
No timestamp alone proves a successful accepted summary or permanent authorization.

## HSD-ES

Authoritative wiki entry:
`https://wiki.ith.intel.com/spaces/HSDESWIKI/pages/954011548/HSD-ES+API`.
Related official pages read: Comments Apis page3167367637; User Apis page3016990262.
Live documentation UI `https://hsdes-api.intel.com/rest/doc/` points to
`https://hsdes-api.intel.com/rest/swagger.json`; retrieved through authenticated Ego browsing.
Local schema `.tmp/project-reporting-w3/hsd-swagger.json`, Swagger2.0, API version0.0.1, basePath/rest.
SHA256 `f10346b6a5a73c17c5e2e0c711679e593cf62bb7f72163cffa1ce7eca1e78113`.
Only documentation content was fetched, not a record/query result.

| Need | Documented operation | What remains to qualify |
| --- | --- | --- |
| Current user | GET `/rest/user`, operationId whoAmI | Exact response identity field and selected auth under current deployment |
| Saved rule | GET `/rest/query/{id}?expand=metadata` | Rule-version/definition response, not just saved ID |
| Membership | GET `/rest/query/execution/{id}` | start_at defaults1, max_results described as End Row; do not assume Jira-style offset/count |
| Article | GET `/rest/article/{id}` with tenant/subject/fields | Full canonical fields/updated/rev mapping |
| Comments | GET `/rest/article/{id}/children?child_subject=comment&fields=id,rev,owner,description` | Response structure and completeness; docs list no paging params here |
| History | GET `/rest/article/{id}/history`, optional rev/fields/showChangedFields | Full revisions documented, exact response shape/completeness still needs sample |
| Attachments | children with child_subject=attachment and binary APIs | Metadata/body authorization and complete bounded capture need separate design/tests |

Important correction: historical facts-only fallback does not mean HSD lacks comments/history endpoints.
They are documented; capability may remain unqualified or partial until an adapter and sample prove it.
The checked Swagger often gives status descriptions without JSON response schemas, so do not invent a
success-shaped fixture and call it deployed compatibility.

Authentication wiki recommends Kerberos/Windows integrated auth. It describes HSD tokens as a
username/password Basic Auth pair requiring `/rest/auth/...`. This does not by itself establish support
for Bearer token auth in the existing `HsdesHttpClient` token mode.
Keep that existing mode explicit and unqualified unless another authoritative reference or bounded
authorized sample proves it. Never send a Jira PAT to HSD, downgrade TLS because sample code does,
or silently change an operator's configured auth mode.

## Implementation Checks

- Jira adapter tests must reject unstable totals, duplicate IDs, partial comments and before/after drift.
- HSD pagination tests must follow documented1-based row semantics, not the existing0/count assumption.
- Response decoders require exact observed/documented payload contract; unsupported shape is explicit
  partial/unsupported, not coerced into a complete empty array.
- Source identity and membership/part coverage stay separate from storage/accepted checkpoints.
- Offline schemas and synthetic transport can prove local refusal/flow; exact live instance/auth
  qualification remains separately authorized and cannot be inferred from this documentation read.
