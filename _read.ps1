$fifo = "c:\Users\wisdo\Desktop\projects\trackwise\services\fifo_service.py"
$lines = [System.IO.File]::ReadAllLines($fifo)
Write-Host "--- record_purchase validation ---"
for ($i=85; $i -le 98; $i++) { Write-Host ("$i`: " + $lines[$i]) }
Write-Host "---"
Write-Host "--- record_expense validation ---"
for ($i=262; $i -le 270; $i++) { Write-Host ("$i`: " + $lines[$i]) }

$app = "c:\Users\wisdo\Desktop\projects\trackwise\app.py"
$lines2 = [System.IO.File]::ReadAllLines($app)
Write-Host "--- month_bounds helper ---"
for ($i=0; $i -le 30; $i++) { Write-Host ("$i`: " + $lines2[$i]) }
Write-Host "--- app config area ---"
for ($i=30; $i -le 45; $i++) { Write-Host ("$i`: " + $lines2[$i]) }

