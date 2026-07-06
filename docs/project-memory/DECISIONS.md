# Decisions and Principles

## D-001 Storage vs execution
NAS is for storage. Do not use it as the intended execution environment.
Use local Windows or Linux/UT execution environments.

## D-002 TEST vs PROD
TEST and PROD must be separated for data security, information security and business continuity.
Development bugs must not interrupt normal company operations.

## D-003 Buy/build/open-source
Do not develop everything internally. Prefer mature open-source and free resources when they
meet security, maintainability and business requirements.

## D-004 Architecture size
Optimize for low-cost business support. Keep systems secure, complete and simple.
Avoid unnecessary platform sprawl.

## D-005 Human + digital employee
Digital employees automate routine work. Staff and leaders retain daily review, exception handling,
approval and accountability where required.

## D-006 Multilingual operation
Chinese-first internal communication, Japanese-first customer communication, English when needed.
System design should support zh-CN/ja-JP/en.

## D-007 Source control classification
Public/shareable engineering assets may go to Git/GitHub only after classification and secret review.
Internal business documents, customer data, bank data, credentials, personal information, internal
strategy and sensitive operating records remain internal.
Never commit secrets or real business data.

## D-008 FULL package definition
A FULL package is self-contained and cleanly deployable. Mixed Copy-Item overlay of old and new
application files is not a FULL deployment.

## D-009 Database change control
SQLAlchemy create_all() does not replace schema migration.
Back up data before migration. Migrations must be explicit, idempotent where possible and tested.

## D-010 Deployment quality gate
Before starting API:
package structure -> required modules -> compile -> backup -> clean replacement -> migration ->
import -> automated tests -> HTTP smoke -> start.
Failure triggers rollback.

## D-011 Project memory
Chat is not the project database. Project state, decisions, WBS, build history, known issues and
next actions are maintained as versioned project-memory documents.
