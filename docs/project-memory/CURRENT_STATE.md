# Current State

## Program status
TLC is building two connected layers in parallel:

### A. Group AI business-support platform
A pragmatic, low-cost AI capability for management and staff, using open-source/free
resources where appropriate, with knowledge bases, tools, digital employees, human review,
security controls and multilingual support.

### B. Request / Sales / Receivables / Bank Reconciliation Platform
Target business chain:
1. Receive and manage original files.
2. Parse request/invoice PDF and Excel.
3. Compare business data.
4. If matched, post validated data into sales records/database.
5. Query and aggregate sales through Web UI.
6. If mismatched, create an easy-to-read business review artifact and review task.
7. Continue to accounts receivable management.
8. Reconcile against bank receipts/statements.
9. Digital employees perform routine processing.
10. Employees and leaders review exceptions and approvals.

## Web UI direction
Dashboard is a business navigation cockpit, not a minimal demo page. It should include:
- Daily TODO
- Performance / KPI
- Business exceptions
- Digital employees
- Request review
- Sales list
- Receivables
- Bank reconciliation
- Leadership review
- Deployment operations
- System/AI health
- Knowledge/tool entrances

## Environment direction
- NAS Y: paths: storage and repository/document storage.
- Windows local: active execution for current development/test workloads.
- Linux/UT/AI server: AI and service workloads as architecture evolves.
- TEST and PROD separated.
- Current TEST database path used in prior deployment commands:
  C:/TLC-BOS/data/test/request_platform_test.db
- Current local Python venv used:
  C:/TLC-BOS/venv/request-employee-platform
- Current local API target:
  127.0.0.1:8018

## Latest delivery state
Build030R2 CLEAN TRUE FULL has been prepared after Build030R1 failed.
Deployment verification is pending and must be recorded before declaring it stable.
