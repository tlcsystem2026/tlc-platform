# Request Employee — Sprint1 Build005

## Run

```powershell
cd apps/request-employee
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="$PWD\src"
python src/main.py --pdf "sample.pdf" --excel "sample.xlsx" --output "difference.xlsx"
```

## Test

```powershell
$env:PYTHONPATH="$PWD\src"
pytest -q
```

Build005 provides a runnable PDF/Excel parse → normalize → compare → Excel difference-report pipeline.
