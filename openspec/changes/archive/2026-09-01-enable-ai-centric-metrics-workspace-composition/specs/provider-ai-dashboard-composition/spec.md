## ADDED Requirements

### Requirement: AI chart composition can start from canonical data blocks
AI dashboard composition SHALL support future chart drafting from Metrics-published canonical data blocks, not only from pre-existing chart recipes.

#### Scenario: AI asks available lego blocks
- **WHEN** a user asks what data elements can be used to build Grafana charts
- **THEN** AI SHALL answer from Metrics context bundle data-block catalog, including canonical dimensions, measures, grain, allowed transforms and evidence capability

#### Scenario: AI generates a draft artifact
- **WHEN** AI generates Grafana JSON or a render spec from data blocks
- **THEN** the artifact SHALL stay in AI Base workspace storage until Metrics validates canonical fields, transforms, provider boundary and Grafana render constraints
