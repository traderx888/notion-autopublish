param(
    [string]$TaskName = "Ciovacco-Weekly-Feed",
    [switch]$WhatIf
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$batchPath = Join-Path $repoRoot "run_ciovacco_weekly.bat"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batchPath`""
$triggerSaturday = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 2:00PM
$triggerSunday = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2:00PM

if ($WhatIf) {
    Write-Host "Would register scheduled task '$TaskName' for $batchPath"
    return
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerSaturday, $triggerSunday) -Description "Capture CiovaccoCapital weekly feed on Saturday and Sunday afternoons" -Force | Out-Null
Write-Host "Registered scheduled task '$TaskName'"
