## MODIFIED Requirements

### Requirement: AI-generated render drafts are validation-gated
AI-generated chart/dashboard drafts SHALL remain unpublished until Metrics validates data surfaces、profile references、series、category fields、range、limits、evidence links、secret safety and workspace boundary.

#### Scenario: Draft passes validation
- **WHEN** AI draft references existing profile、approved chart recipe、approved series、approved render shape and a workspace key matching the selected provider/profile boundary
- **THEN** Metrics MAY store the draft as unpublished/personal or publish it according to configured approval policy
- **THEN** Metrics SHALL record validation/audit metadata

#### Scenario: Draft workspace key does not match profile
- **WHEN** AI draft contains `workspace_key` for one provider/profile but artifact content references another profile/provider
- **THEN** Metrics SHALL reject the draft with structured findings
- **THEN** Metrics SHALL NOT generate importable Grafana JSON from it

#### Scenario: Draft fails validation
- **WHEN** AI draft contains unapproved datasource、raw JQL/EQL、provider-native field literal、secret-like value、unbounded SQL、unsupported chart id or unsupported profile
- **THEN** Metrics SHALL reject the draft with structured findings and SHALL NOT generate importable Grafana JSON from it

### Requirement: AI chart composition can start from canonical data blocks
AI dashboard composition SHALL support future chart drafting from Metrics-published canonical data blocks, not only from pre-existing chart recipes.

#### Scenario: AI asks available lego blocks
- **WHEN** a user asks what data elements can be used to build Grafana charts
- **THEN** AI SHALL answer from Metrics context bundle data-block catalog, including canonical dimensions, measures, grain, allowed transforms and evidence capability

#### Scenario: AI generates a draft artifact
- **WHEN** AI generates Grafana JSON or a render spec from data blocks
- **THEN** the artifact SHALL stay in AI Base workspace storage until Metrics validates canonical fields, transforms, provider boundary, workspace key and Grafana render constraints
