# Sprint1 Build009

## Delivered
- PostgreSQL save option wired into `tokyo_main.py`
- `--save-db` CLI flag
- Docker Compose for Request Employee PostgreSQL test DB
- PowerShell one-pair run script
- PowerShell DB initialization script
- `.env.example`
- Repository import smoke test

## Run DB

```powershell
docker compose -f docker/docker-compose.request-db.yml up -d
```

## Init DB

```powershell
$env:PGPASSWORD="tlc"
.\scripts\request-init-db.ps1 -HostName localhost -Database tlc_platform -User tlc
```

## Run single pair

```powershell
.\scripts\request-run-tokyo.ps1 `
  -Pdf "Y:\TLC-BOS\Documents\RequestEmployee\PDF\東京恋人請求書_税込_LY01006_1230_新川_取消.pdf" `
  -Excel "Y:\TLC-BOS\Documents\RequestEmployee\Excel\東京恋人請求書_税込_LY01006_1230_新川_取消.xlsx" `
  -SaveDb
```

## Known limitations
- PostgreSQL is optional and currently used for test persistence.
- Production DB integration is not enabled by default.
