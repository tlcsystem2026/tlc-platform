# Build034 Business Acceptance Guide

## Main entry points

- Sales request review and formal ledger:
  `http://127.0.0.1:8000/requests/review-workbench`
- Bank statement import:
  `http://127.0.0.1:8000/bank-import`
- TLC Code Master:
  `http://127.0.0.1:8000/tlc-code-master`
- Bank account profile:
  `http://127.0.0.1:8000/tlc-bank-account-master`
- Customer Master:
  `http://127.0.0.1:8000/tlc-customer-master`
- Customer reconciliation workbench:
  `http://127.0.0.1:8000/customer-reconciliation-workbench`
- API documentation:
  `http://127.0.0.1:8000/docs`

## Business acceptance sequence

1. Create or verify Customer Master, including bank-name aliases.
2. Import the request Excel/PDF pair and review comparison errors.
3. Allow matched requests to enter Pending Review.
4. Approve the request and post it to the formal Sales Ledger.
5. Import the bank CSV.
6. Run automatic customer matching.
7. Resolve UNMATCHED or AMBIGUOUS receipts manually when necessary.
8. Select the customer in the reconciliation workbench.
9. Verify previous/current request and bank cutoffs.
10. Calculate:
    opening outstanding + period sales - period receipts = closing outstanding.
11. Review sales and receipt details.
12. Confirm and save the reconciliation.
13. Start the next period and verify automatic opening-balance carry-forward.

## Acceptance result

The Build034 milestone is accepted when:
- the focused acceptance test passes;
- the six main pages return HTTP 200;
- a customer request reaches the formal Sales Ledger;
- a bank receipt is matched or manually assigned;
- reconciliation is calculated and confirmed;
- the next period automatically receives the prior closing outstanding.
