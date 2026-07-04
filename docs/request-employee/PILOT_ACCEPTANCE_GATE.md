# Pilot Acceptance Gate

## Minimum gate for controlled pilot
- [ ] Preflight passes
- [ ] Smoke test passes
- [ ] Two real PDF/Excel pairs process without crash
- [ ] Output generated for each pair
- [ ] Human can read Excel/HTML reports
- [ ] Original files remain untouched
- [ ] Parser failures are clearly marked
- [ ] Duplicate second run is skipped unless `-Force`

## Not production-ready until
- [ ] 20+ real pairs tested
- [ ] false positive rate documented
- [ ] OCR fallback implemented if scanned PDFs appear
- [ ] database persistence reviewed
- [ ] operator signs off on workflow
