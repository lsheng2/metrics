# Provider Source Authority

This reference preserves the provider research requirement previously embedded in AGENTS.md.
It is not a live-access authorization or a claim that a provider has been qualified.

- Jira Data Center REST: https://developer.atlassian.com/server/jira/platform/rest/v10000/
- Versioned Jira Server/Data Center references: https://docs.atlassian.com/software/jira/docs/api/REST/
- Jira Software Agile/Data Center: https://docs.atlassian.com/jira-software/REST/
- Jira Cloud, only for a Cloud target: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
- Intel HSD-ES API: https://wiki.ith.intel.com/spaces/HSDESWIKI/pages/954011548/HSD-ES+API

Check the relevant official source before changing authentication, endpoint shape, paging,
query syntax, field identity, permission behavior or response interpretation. Saved-query/UI
observations are configuration evidence, not a replacement for the API contract.
If the needed source is unavailable, state the uncertainty and obtain the missing reference;
do not infer HSD behavior from Jira or claim live qualification from a synthetic fixture.

Project-specific scope/status/severity semantics belong to the saved scope/provider profile.
The detailed historical agent guides remain available in Git at `eb8de2e:AGENTS.md` and
`eb8de2e:CLAUDE.md`; the current execution rules are solely in `AI_CONTRACT.md`.
