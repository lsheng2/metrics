## ADDED Requirements

### Requirement: AI render artifacts are validated as render config inputs
Grafana render config SHALL support AI-authored draft artifacts as inputs only after they satisfy the same validation rules as developer-authored render configs.

#### Scenario: AI render artifact uses approved recipe
- **WHEN** an AI artifact references an approved chart recipe, profile id, range, render shape, category field and value fields
- **THEN** the validator SHALL accept the artifact and return a normalized render config preview
- **THEN** generated Grafana JSON SHALL be derived from the normalized render config rather than directly trusting arbitrary AI JSON

#### Scenario: AI render artifact uses data blocks
- **WHEN** an AI artifact starts from canonical data blocks instead of a pre-existing chart recipe
- **THEN** the validator SHALL require approved canonical fields, allowed transforms, provider boundary and render constraints before the artifact can become publishable
- **THEN** unsupported data-block semantics SHALL be reported as a Metrics-owned recipe or aggregate gap

#### Scenario: AI render artifact includes unsafe content
- **WHEN** an AI artifact includes provider-native query literals, raw SQL, unapproved datasource ids, secrets or local filesystem paths
- **THEN** validation SHALL fail and SHALL report the unsafe field paths
