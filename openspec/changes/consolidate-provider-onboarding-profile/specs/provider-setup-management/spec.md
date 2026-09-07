## MODIFIED Requirements

### Requirement: Provider setup flow is template-driven
Provider Setup SHALL use provider setup templates to define provider onboarding, connection settings, temporary local credentials, default capability/readiness copy and legacy mapping defaults without duplicating the full page per provider.

#### Scenario: User configures provider onboarding
- **WHEN** 用户 opens New Profile or edits an existing provider profile
- **THEN** the main editor SHALL show provider-level connection/onboarding fields before source or mapping JSON
- **AND** the editor SHALL collect base URL and provider authentication method before showing method-specific credential fields
- **AND** credential reference SHALL remain an internal or advanced compatibility setting rather than a primary user-facing control
- **AND** onboarding status SHALL render as a system-derived status and SHALL NOT be user-selectable
- **AND** saved token fields SHALL NOT be echoed back as plain text when the editor is reopened
- **AND** blank temporary credential fields on edit SHALL preserve existing stored credentials unless the user explicitly clears them
- **AND** enabling the provider profile SHALL NOT require Advanced JSON field bindings or chart bindings unless supported chart bindings are explicitly configured

#### Scenario: Authentication details are provider and method specific
- **WHEN** the user selects a provider and authentication method in Provider Setup
- **THEN** the editor SHALL render only the credential fields used by that provider and method
- **AND** Jira API token / PAT SHALL not show username, password, HSD-ES, or GitHub credential copy
- **AND** HSD-ES Username + password SHALL show username and password fields with provider-neutral helper text
- **AND** HSD-ES Bearer token and GitHub Personal access token SHALL not activate each other's token panels
- **AND** form submission SHALL ignore credential fields that do not belong to the selected provider authentication method

#### Scenario: Credential inputs distinguish tokens from plain-text onboarding fields
- **WHEN** a provider profile contains temporary local credentials
- **THEN** username, email and password fields SHALL render as editable plain text
- **AND** token fields SHALL render as masked stars when already saved
- **AND** submitting the masked stars SHALL preserve the existing token value
- **AND** typing a new token SHALL replace the saved token and render as masked stars after save

#### Scenario: Configuration forms use aligned field grids
- **WHEN** users edit provider profiles or bug trend scopes on desktop or mobile
- **THEN** related input/select controls SHALL have consistent heights and aligned label rows
- **AND** the page SHALL avoid horizontal overflow in desktop and phone viewports

#### Scenario: User tests provider profile connectivity
- **WHEN** a user clicks Test Connection in the provider profile editor
- **THEN** the system SHALL test the current provider profile connection without saving the profile
- **AND** Jira profiles SHALL use the configured Jira connection to request server information
- **AND** HSD-ES profiles SHALL use the configured saved-query probe when query id, tenant and subject are available
- **AND** HSD-ES profiles without a probe source SHALL return a configuration-required result instead of guessing an undocumented endpoint
- **AND** the rendered result SHALL not expose raw token values

#### Scenario: Source-specific settings are advanced compatibility details
- **WHEN** profile source population, field bindings, value mappings or chart bindings are still needed by existing runtime paths
- **THEN** the UI SHALL keep them under Advanced JSON configuration
- **AND** the primary copy SHALL state that concrete JQL/saved-query/project range belongs to Scope Config

### Requirement: Profile packages are portable and non-secret
Provider Profile export/import SHALL preserve provider connection references and default mapping information without leaking credentials or runtime data by default.

#### Scenario: User exports a provider profile package
- **WHEN** a profile contains `connection_settings.credential_ref`
- **THEN** the exported package SHALL include the credential reference
- **AND** the exported package SHALL exclude profile-local temporary credentials and keys containing token, password, secret or credential material except the non-secret `credential_ref`
- **AND** the package SHALL still exclude provider facts, sync cursors, calculation outputs and AI artifacts

#### Scenario: Runtime resolves local profile credentials before settings fallback
- **WHEN** a Jira or HSD-ES provider profile contains profile-local temporary credentials
- **THEN** sync commands SHALL use those credentials for that profile
- **AND** sync commands SHALL fall back to deployment settings when profile-local credentials are absent or settings references are used
