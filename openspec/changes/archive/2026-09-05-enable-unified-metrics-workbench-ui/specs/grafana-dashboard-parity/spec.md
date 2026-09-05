## ADDED Requirements

### Requirement: Grafana evidence interactions synchronize with workbench state
Grafana panels that participate in the unified workbench SHALL expose Metrics-approved evidence interaction metadata so a selected data point can update workbench PageQueryState and ticket evidence.

#### Scenario: Grafana panel exposes bucket-series evidence
- **WHEN** a Grafana panel declares `bucket_series` evidence capability
- **THEN** its Metrics contract SHALL identify the fields needed to resolve calculation run or fact snapshot, bucket id and series name
- **AND** its user-facing click/data-link behavior SHALL carry those values to the workbench or to a Metrics evidence URL accepted by the workbench

#### Scenario: Grafana data link is opened inside workbench
- **WHEN** 用户 clicks a Grafana data link for an evidence-backed bucket/series point inside the workbench
- **THEN** workbench SHALL update PageQueryState from the validated link parameters
- **AND** evidence pane SHALL refresh without requiring the user to leave the unified UI

#### Scenario: Grafana panel cannot emit a valid selection
- **WHEN** a Grafana panel cannot map interaction to Metrics-approved run/snapshot, bucket and series fields
- **THEN** the panel SHALL be treated as read-only for point-level evidence
- **AND** the workbench SHALL show range-only, summary-only or unsupported evidence state according to the chart contract

### Requirement: Workbench embeds Grafana at panel scope
Grafana content embedded in the unified workbench primary chart pane SHALL prefer compact panel-level embed or solo panel URLs rather than the full Grafana dashboard page.

#### Scenario: Workbench shows a Grafana chart pane
- **WHEN** active renderer is Grafana stock panel
- **THEN** workbench SHALL render a compact panel-level Grafana embed sized for the chart pane
- **AND** it SHALL avoid displaying Grafana global navigation, dashboard sidebar, unrelated panels or admin chrome inside the primary chart container

#### Scenario: User needs full Grafana page
- **WHEN** 用户 needs Grafana dashboard editing, diagnostics or admin controls
- **THEN** workbench MAY provide a separate full-dashboard link or diagnostics/admin pane
- **AND** that full Grafana page SHALL NOT be the default embedded chart pane for normal analysis

#### Scenario: Panel embed cannot satisfy interaction requirements
- **WHEN** compact panel embed cannot reliably support Metrics-approved evidence selection sync
- **THEN** implementation SHALL keep the Metrics-owned reference renderer as the interactive evidence path
- **AND** future work MAY move the Grafana path to App Plugin or Scenes instead of expanding the primary pane to full Grafana UI

### Requirement: Grafana iframe state is not source of truth
Workbench SHALL NOT treat Grafana iframe internal state as authoritative for Metrics evidence; all evidence queries SHALL be derived from workbench PageQueryState and Metrics-validated chart/evidence contracts.

#### Scenario: Grafana variable differs from workbench state
- **WHEN** Grafana iframe variable, time picker or local panel state differs from workbench PageQueryState
- **THEN** Metrics evidence request SHALL follow workbench PageQueryState
- **AND** shell SHALL show a sync or stale-state indicator when the mismatch affects visible chart/evidence consistency

#### Scenario: Workbench refreshes Grafana panel
- **WHEN** workbench PageQueryState changes profile, range or chart
- **THEN** Grafana pane SHALL be reloaded or updated with URL variables that reflect the shell state
- **AND** evidence pane SHALL NOT rely on reading hidden Grafana iframe state
