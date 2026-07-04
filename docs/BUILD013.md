# Sprint1 Build013 — Comparison Reliability

## Delivered
- Line amount reconciliation: quantity × unit price = amount
- Line sum vs subtotal reconciliation
- Subtotal + tax vs total reconciliation
- Parser failure vs business difference classification
- Stronger line matching:
  1. product code
  2. exact product name
  3. fuzzy product name + amount bonus
- Reconciliation JSON output
- Unit tests

## Pilot gate
Build013 is the reliability layer before stability hardening.

## Next Build014
- regression tests
- duplicate/idempotency protection
- failure isolation
- DB transaction hardening
- smoke test script
