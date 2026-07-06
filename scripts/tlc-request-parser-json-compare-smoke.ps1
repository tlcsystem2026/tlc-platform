param([int]$Port=8018)
$ErrorActionPreference="Stop"
$Repo="Y:\TLC-BOS\Repository\projects\tlc-platform"
$Body=@{legal_entity_id="TEST-JP-01";pdf_json_path="$Repo\apps\request-employee-platform\tests\fixtures\request_pdf_parser_sample.json";excel_json_path="$Repo\apps\request-employee-platform\tests\fixtures\request_excel_parser_sample.json"}|ConvertTo-Json
$r=Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/api/requests/compare-parser-json" -ContentType "application/json" -Body $Body
$r|ConvertTo-Json -Depth 10
if($r.status -notmatch "matched"){throw "Expected matched"}
Write-Host "Parser JSON auto compare smoke PASSED."
