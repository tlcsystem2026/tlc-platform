# Request Employee Sales Ledger Flow

## Business rule

1. PDF and Excel consistent:
   - Register request content into:
     - `Y:\TLC-BOS\Documents\RequestEmployee\Sales\sales_ledger.xlsx`

2. PDF and Excel inconsistent:
   - Do not register into Sales Ledger.
   - Copy original PDF and Excel into:
     - `Y:\TLC-BOS\Documents\RequestEmployee\Error`
   - Create:
     - `error_reason.json`

## Run

```powershell
cd Y:\TLC-BOS\Repository\projects\tlc-platform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\request-run-sales-flow-local.ps1
```
