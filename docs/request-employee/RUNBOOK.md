# Request Employee Runbook

## 1. Prepare folders

```powershell
.\scripts\request-check-folders.ps1
```

## 2. Put business files

Put original PDFs into:

```text
Y:\TLC-BOS\Documents\RequestEmployee\PDF
```

Put original Excel files into:

```text
Y:\TLC-BOS\Documents\RequestEmployee\Excel
```

Original files must never be modified.

## 3. Run batch

```powershell
.\scripts\request-run-batch.ps1
```

## 4. Check output

```powershell
.\scripts\request-validate-output.ps1
.\scripts\request-open-output.ps1
```

## 5. Review generated files

Each request folder should contain:

- `pdf.json`
- `excel.json`
- `differences.json`
- `differences.xlsx`
- `differences.html`

## 6. Commit code only

Business files under `Y:\TLC-BOS\Documents\RequestEmployee` are not committed to Git.
