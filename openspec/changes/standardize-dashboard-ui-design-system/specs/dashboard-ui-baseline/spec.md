## MODIFIED Requirements

### Requirement: Dashboard UI uses shared design-system tokens and components
Dashboard UI SHALL define reusable design-system tokens and component classes for typography, controls, badges, form grids, action bars, dirty-state feedback and panels. Page templates SHALL compose those shared classes instead of creating independent button/font/layout variants for each editor.

#### Scenario: Setup editor renders form controls
- **WHEN** a setup editor renders input, select, textarea, required marker, status marker or action buttons
- **THEN** it SHALL use dashboard-level form/action/tag classes backed by shared CSS tokens
- **AND** tags SHALL use badge typography rather than button/input typography
- **AND** action buttons in the same action bar SHALL have consistent height, spacing and responsive stacking

#### Scenario: User edits a setup field
- **WHEN** a user changes a field value before saving
- **THEN** the edited field cell SHALL show a visible unsaved highlight
- **AND** the field label SHALL show a concise unsaved marker
- **AND** the editor SHALL expose both save and cancel-editing actions without requiring the user to search elsewhere

#### Scenario: UI changes touch buttons or fonts
- **WHEN** a future change modifies Dashboard UI buttons, fonts, tags, form grids or editor actions
- **THEN** the change SHALL include a design-system validation check or explain why the existing shared component is insufficient
- **AND** browser validation SHALL cover desktop and phone widths for overflow, button height consistency and field alignment
