param(
  [string]$HostName = "localhost",
  [string]$Database = "tlc_platform",
  [string]$User = "tlc"
)

$RepoRoot = "Y:\TLC-BOS\Repository\projects\tlc-platform"
$Schema = Join-Path $RepoRoot "database\schema\005_request_employee_tables.sql"

Write-Host "Applying schema: $Schema"
psql -h $HostName -U $User -d $Database -f $Schema
