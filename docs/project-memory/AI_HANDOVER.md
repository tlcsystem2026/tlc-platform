# TLC Project AI Handover

## Purpose
This file is the short handover entry point for a new AI conversation.
Read this file first, then CURRENT_STATE.md, DECISIONS.md, WBS.md, BUILD_HISTORY.md,
KNOWN_ISSUES.md and NEXT_ACTIONS.md before proposing code or a deployment package.

## Company context
- Group operates two Japanese companies and two Chinese companies.
- President's native language is Chinese.
- Internal daily communication is mainly Chinese.
- Customer communication is mainly Japanese.
- English is used when required for overseas customers and external resources.
- Main customers are Japanese, with additional Chinese and other overseas customers.

## Core engineering principles
- NAS is storage only; do not treat NAS as the execution environment.
- Execution environments are local Windows and Linux/UT environments.
- TEST and PROD must be physically/logically separated.
- Protect business continuity: an in-progress bug must not bring down production.
- Prefer open-source and free resources where suitable.
- Do not build everything from scratch.
- Goal: low-cost support for real business operations.
- Systems should be secure, complete, simple, maintainable, and not unnecessarily large.
- Human review and leadership approval remain part of business workflows.
- Digital employees automate routine work but do not remove required controls.
- Git/GitHub content and internal-only company archives must be classified separately.
- FULL package means clean, self-contained baseline; do not mix-overlay old files and call it FULL.
- Database migration is explicit; create_all() is not a migration strategy.
- Deployment must use quality gates and rollback.

## Current stable/recovery line
- Latest package prepared in the prior conversation: Build030R2 CLEAN TRUE FULL.
- Package name: TLC_BUILD030R2_CLEAN_TRUE_FULL.zip
- Intended runtime version: 0.30.2-clean-true-full.
- Build030R1 failed Import Gate because src.domain.deploy was missing.
- Build030R2 added that missing module, strengthened preflight, and added regression tests.
- Deployment success of Build030R2 is NOT yet confirmed in this handover. Treat it as pending verification.

## Three active program lines
1. Restore and improve the complete Dashboard, including the richer digital-employee version.
2. Continue request/invoice business platform implementation:
   PDF/Excel compare -> matched data -> sales database -> Web query/statistics;
   mismatches -> review/error workflow; then receivables and bank reconciliation.
3. Continue overall AI business-support deployment:
   AI server, knowledge base, tools, digital employees, monitoring, permissions and operational integration.

## Immediate rule for a new conversation
Do not immediately generate Build031.
First:
1. Read project-memory documents.
2. Ask for or verify Build030R2 deployment result.
3. Confirm repository working state and stable baseline.
4. Only then plan Build031.
