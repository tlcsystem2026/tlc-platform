# Build006

Adds product-code/name line matching, JSON intermediate artifacts, logging, and directory batch processing.

Run batch:

```powershell
$env:PYTHONPATH="$PWD\src"
python src/batch_main.py --pdf-dir "PDF" --excel-dir "Excel" --output-dir "Output"
```

Pairing currently uses identical filename stems, e.g. `LY01006.pdf` with `LY01006.xlsx`.
