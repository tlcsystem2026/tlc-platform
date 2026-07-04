# Request Employee Acceptance Checklist

## Folder setup

- [ ] `Y:\TLC-BOS\Documents\RequestEmployee\PDF` exists
- [ ] `Y:\TLC-BOS\Documents\RequestEmployee\Excel` exists
- [ ] `Y:\TLC-BOS\Documents\RequestEmployee\Output` exists

## Input files

- [ ] PDF files are original files
- [ ] Excel files are original files
- [ ] Matching can be done by invoice number or filename similarity

## Batch execution

- [ ] Batch script runs without Python import errors
- [ ] `batch_summary.json` is generated
- [ ] Each paired request has an output folder

## Output review

- [ ] `pdf.json` is generated
- [ ] `excel.json` is generated
- [ ] `differences.json` is generated
- [ ] `differences.xlsx` is generated
- [ ] `differences.html` is generated

## Business review

- [ ] Request number is correct
- [ ] Request date is correct
- [ ] Customer name is correct
- [ ] Total amount is correct
- [ ] Product lines are extracted
- [ ] Differences are understandable
- [ ] False positives are recorded for parser improvement
