# Architecture Overview

## 1. AI business-support architecture
Users / Leaders / Staff
-> Business Dashboard
-> Digital Employee Orchestration
-> AI Applications and Workflows
-> Knowledge Bases + Tools
-> Local/approved models and external services where permitted
-> Business systems and controlled connectors
-> Audit / permissions / monitoring

Candidate capabilities should be evaluated before adoption rather than automatically self-built:
- Local model serving
- Workflow/orchestration
- Retrieval knowledge bases
- OCR/document parsing
- Tool protocols/connectors
- Monitoring and logging
- Authentication and role control

## 2. Request-to-cash platform architecture
Original Documents
-> Document Registry / Managed Storage
-> PDF/Excel Parsers
-> Normalization
-> Comparison Engine
-> [Matched] Sales Posting
-> Sales DB / Web Search / Statistics
-> Receivables
-> Bank Statement Parsing
-> Receipt Matching
-> Exception Review / Leadership Review

Mismatch branch:
Comparison Engine
-> Review Task
-> Human-readable comparison artifact
-> Employee correction
-> Re-run / approval
-> downstream posting

## 3. Data principles
- Original files retained with traceability.
- Database stores normalized operational records and status.
- Business users should not be forced to read JSON.
- JSON may remain an internal machine artifact.
- Every automated posting should be traceable to source files and compare result.
- Multi-legal-entity design is required for the group.

## 4. Environment topology
NAS: storage / archives / packages / documents
Windows TEST: local application execution and test DB
Linux/UT/AI server: AI services and selected backend workloads
PROD: separate deployment and data boundary; not a continuation of TEST
