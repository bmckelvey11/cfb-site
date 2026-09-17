<#
.SYNOPSIS
  Re-registers the six CFB Windows scheduled tasks onto one aligned grid and a
  non-interactive principal.

.DESCRIPTION
  Two problems this fixes, both found 2026-09-10:

  1. Every task was registered LogonType=Interactive, so each firing popped a
     visible console window -- ~15 a day. S4U runs the same account without a
     desktop session, so the window is gone. (The Task Scheduler "Hidden" flag
     does NOT do this; it only hides the task from the console's task list.)

  2. The start times were scattered across three phases and two intervals
     (:00, :15, :30 on 5h and 6h), so nothing ever lined up. 5h can never align
     with 6h, so CFB-AN-History moves to 6h -- 5 runs/day becomes 4. That is a
     collection-cadence change, deliberate: the AN endpoint returns full history
     per game, so cadence sets freshness and retry count, not resolution.

  The grid is minute-staggered rather than simultaneous. Only refresh_cfbd.py
  writes cfb.duckdb (full rebuild, ~16 min measured 2026-09-10); the snapshot
  jobs write independent files and can share a slot safely. CFB-CFBD-Daily
  (writer) and CFB-OverZero-Slate (reader + npm build) stay off the burst with
  the rebuild window between them.

      00:00 / 06:00 / 12:00 / 18:00  CFB-Odds-Snapshot
      00:05 / 06:05 / 12:05 / 18:05  CFB-PT-Snapshot
      00:10 / 06:10 / 12:10 / 18:10  CFB-AN-History
      05:00 daily                    CFB-CFBD-Daily      (rebuild, ends ~05:16)
      06:15 daily                    CFB-Pinnacle-Snapshot
      Wed 09:20 and 18:20            CFB-OverZero-Slate
      Tue 04:30                      CFB-Massey-Weekly   (ends before the rebuild)

  Idempotent: re-running sets the same principal and triggers again.

.PARAMETER WhatIf
  Show what would change without touching the tasks.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\schedule_cfb_tasks.ps1
#>
[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'

# S4U needs the qualified account name; the bare username registers as
# "incorrectly formatted" on some builds.
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Limited

function Repeating6h {
    # -Once + RepetitionInterval is the only way to express "every N hours
    # forever"; a plain -Daily trigger cannot repeat within the day.
    param([string]$At)
    $t = New-ScheduledTaskTrigger -Once -At $At `
        -RepetitionInterval (New-TimeSpan -Hours 6) `
        -RepetitionDuration ([TimeSpan]::MaxValue)
    $t
}

$schedule = [ordered]@{
    'CFB-Odds-Snapshot'     = { Repeating6h '00:00' }
    'CFB-PT-Snapshot'       = { Repeating6h '00:05' }
    'CFB-AN-History'        = { Repeating6h '00:10' }
    'CFB-CFBD-Daily'        = { New-ScheduledTaskTrigger -Daily -At '05:00' }
    'CFB-Pinnacle-Snapshot' = { New-ScheduledTaskTrigger -Daily -At '06:15' }
    'CFB-OverZero-Slate'    = {
        @(
            New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At '09:20'
            New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At '18:20'
        )
    }
    'CFB-Massey-Weekly'     = { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At '04:30' }
}

foreach ($name in $schedule.Keys) {
    if (-not (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue)) {
        Write-Warning "$name is not registered; skipping."
        continue
    }
    if (-not $PSCmdlet.ShouldProcess($name, 'set S4U principal and aligned trigger')) {
        continue
    }
    $triggers = & $schedule[$name]
    try {
        Set-ScheduledTask -TaskName $name -Principal $principal -Trigger $triggers | Out-Null
        $info = Get-ScheduledTaskInfo -TaskName $name
        "OK   {0,-22} next {1}" -f $name, $info.NextRunTime
    }
    catch {
        "FAIL {0,-22} {1}" -f $name, $_.Exception.Message
    }
}
