param(
    [string]$TaskName = "Liquidity-Tracker",
    [switch]$WhatIf
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$batchPath = Join-Path $repoRoot "run_liquidity_tracker.bat"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batchPath`""
$triggerMorning = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 9:00AM
$triggerEvening = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 6:00PM

if ($WhatIf) {
    Write-Host "Would register scheduled task '$TaskName' for $batchPath"
    return
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerMorning, $triggerEvening) -Description "Run the H-model liquidity tracker on weekdays" -Force | Out-Null
Write-Host "Registered scheduled task '$TaskName'"
