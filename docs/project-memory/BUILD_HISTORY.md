# Build History

## Earlier line
Multiple iterative builds established Dashboard, deployment controls, parser work, database status,
sales/review directions and Japan Post Bank parsing. Exact historical package inventory should be
reconciled from repository tags/files before formal release auditing.

## Build028
Referenced by legacy tests. Legacy version expectations later polluted newer FULL deployments.

## Build029 / 029R1
Recovery-related line. Legacy tests expected older runtime versions and conflicted with newer builds.

## Build030 TRUE FULL
Goal: restore a complete baseline after missing src.db and mixed-version failures.
Observed issues:
- Existing SQLite schema lacked legal_entities.created_at.
- Old tests remained mixed with new version.
- Deploy API contract was degraded/inconsistent.
- Dashboard became simplified and lost richer digital-employee content.
Lesson: overlay copying is not a clean FULL strategy; create_all() is not migration.

## Build030R1 CLEAN TRUE FULL
Goals:
- clean application replacement
- TEST DB backup
- additive schema migration
- import/test/smoke gates
- rollback
Result: FAILED Import Gate.
Exact error:
ModuleNotFoundError: No module named 'src.domain.deploy'
Root cause:
deploy route imported DeployRequest/DeployResult from a module omitted from the FULL package.
Quality failure:
Preflight did not include this transitive required module.

## Build030R2 CLEAN TRUE FULL
Prepared correction:
- adds src/domain/deploy.py
- restores typed deploy request/result contract
- rejects path traversal and non-ZIP package names
- strengthens required-module/import preflight
- adds regression tests for the exact omission
- retains clean replacement, DB backup/migration and rollback policy
Status: PENDING USER DEPLOYMENT VERIFICATION.
Do not call stable until verified.
