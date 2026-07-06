# ADR-004 Controlled Web Deploy

Status: Accepted

Dashboard may provide a deploy button only through a controlled TEST-local deployment endpoint.

Rules:
- Only ZIP package filename is accepted.
- Package must be under `Y:\TLC-BOS\Downloads`.
- No arbitrary command input.
- Calls fixed script: `scripts\tlc-deploy-package-local.ps1`.
- PROD deploy is not supported from this endpoint.
