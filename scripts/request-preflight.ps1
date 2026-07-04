$ErrorActionPreference="Stop"
$Repo="Y:\TLC-BOS\Repository\projects\tlc-platform"
$App="$Repo\apps\request-employee"
$DocBase="Y:\TLC-BOS\Documents\RequestEmployee"
Write-Host "TLC Request Employee Pilot Preflight"
$checks=@()
function Add-Check($Name,$Ok,$Detail){$script:checks += [PSCustomObject]@{Name=$Name;OK=$Ok;Detail=$Detail}}
Add-Check "Repository exists" (Test-Path $Repo) $Repo
Add-Check "App exists" (Test-Path $App) $App
Add-Check "PDF folder exists" (Test-Path "$DocBase\PDF") "$DocBase\PDF"
Add-Check "Excel folder exists" (Test-Path "$DocBase\Excel") "$DocBase\Excel"
Add-Check "Output folder exists" (Test-Path "$DocBase\Output") "$DocBase\Output"
try { $py=(python --version 2>&1); Add-Check "Python available" $true $py } catch { Add-Check "Python available" $false $_.Exception.Message }
try { $git=(git --version 2>&1); Add-Check "Git available" $true $git } catch { Add-Check "Git available" $false $_.Exception.Message }
$checks | Format-Table -AutoSize
if ($checks | Where-Object {$_.OK -eq $false}) { throw "Preflight failed. Fix failed checks before pilot." }
Write-Host "Preflight PASSED."
