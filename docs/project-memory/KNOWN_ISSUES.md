# Known Issues and Risks

## KI-001 Build030R2 not yet verified
Severity: High
Status: VERIFY
Action: capture deployment result before Build031.

## KI-002 Dashboard regression
Severity: High
The richer Dashboard with digital employees and other business content was lost/simplified.
Action: restore from known-good design/code evidence, not from memory alone.

## KI-003 Long-chat version contamination
Severity: High
Old build assumptions can leak into new packages.
Action: use project memory + repository baseline + current-version tests.

## KI-004 NAS path execution behavior
Severity: Medium/High
Y: maps to NAS/UNC and Python/watch reload behavior has caused redirects, slowness and reload issues.
Action: preserve principle that NAS is storage, local execution is preferred.

## KI-005 Database migration maturity
Severity: High
Additive ad-hoc migration is only an interim baseline.
Action: adopt disciplined migration/version tracking before PROD.

## KI-006 Business-readable exception output
Severity: High
JSON-only mismatch output is unsuitable for business operations.
Action: HTML/Excel/PDF-style readable comparison artifact and review UI.

## KI-007 Stable release evidence
Severity: High
A generated package is not automatically a stable release.
Action: record test result, deployment result, smoke result and rollback evidence.

## KI-008 Sensitive data classification
Severity: High
Customer, bank and internal company information must not leak to public repositories or unsuitable AI services.
Action: classification checklist and secrets scanning.
