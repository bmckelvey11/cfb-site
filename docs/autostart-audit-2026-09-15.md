# Autostart and scheduled-task audit — 2026-09-15

**Question.** Console windows keep popping up. What spawns them, and is anything
that runs a shell or script on this machine malicious? (Context: confirmed
compromise on 2026-09-09; see memory `machine-compromise-2026-09-09`.)

**Method.** Read-only enumeration on 2026-09-15 13:25 ET: every scheduled task
(all paths) with action, trigger, hidden flag and last result; HKCU/HKLM `Run` and
`RunOnce`; both Startup folders with `.lnk` targets resolved; cmd.exe `AutoRun`;
every PowerShell profile that loads (pwsh and legacy, both under OneDrive);
WMI `__EventConsumer`; PE subsystem of the two console-adjacent binaries;
Authenticode on MEGAcmd. Task Scheduler history is disabled, so launches could
not be confirmed from the event log.

## Cause of the popups

The seven `CFB-*` tasks. Each runs a `.cmd` wrapper directly, as an interactive
task with `Hidden=False`, so Task Scheduler opens a console for every firing.
Combined cadence is roughly a dozen a day at irregular offsets.

| task | cadence |
|---|---|
| CFB-AN-History | every 5h |
| CFB-PT-Snapshot | every 6h |
| CFB-Odds-Snapshot | every 6h |
| CFB-Odds-Snapshot-Saturday | every 2h, Saturdays |
| CFB-OverZero-Slate | twice weekly |
| CFB-Pinnacle-Snapshot | daily 08:00 |
| CFB-CFBD-Daily | daily 05:00 |

Nothing else on the machine spawns a console: `rclone-b2-mount` already runs
through `conhost --headless`, and `MEGAcmdUpdater.exe` (every 2h) is a GUI-
subsystem binary, signed by Mega Limited.

**Fix** (not applied by the agent: the permission classifier blocks
`Set-ScheduledTask`). Run once in PowerShell:

```powershell
Get-ScheduledTask -TaskName 'CFB-*' | ForEach-Object { $a=$_.Actions[0]; $exe=$a.Execute.Trim('"'); $args="--headless `"$exe`" $($a.Arguments)".Trim(); Set-ScheduledTask -TaskName $_.TaskName -Action (New-ScheduledTaskAction -Execute 'C:\Windows\System32\conhost.exe' -Argument $args) | Out-Null; "$($_.TaskName) -> conhost --headless" }
```

Verify with `Start-ScheduledTask CFB-PT-Snapshot`: no window, and a new row in
`data/logs/task_runs.csv`.

## Malware check: nothing found

- **CFB `.cmd` wrappers** (5 task scripts + `task_ledger.cmd`): only the repo's
  venv Python, `npm run build`, and one `powershell -NoProfile` call to format a
  timestamp. No network, no download, no registry, no other exec. The uncommitted
  edits on them add the run ledger only.
- **Run keys**: Chrome, OneDrive, Steam, LGHUB, Overwolf, Google Drive, pCloud,
  Perplexity, Acrobat sync, App Group, Discord, Docker, Directory Opus, Realtek,
  iCUE, Logitech, SecurityHealth. All vendor paths under Program Files. RunOnce empty.
- **Startup folder**: Directory Opus, OneCommander hotkeys, Send to OneNote,
  `mount-b2.cmd` (rclone mount to X:, `--no-console`), and `pango.lnk`, whose
  target `%LOCALAPPDATA%\pango\pango.exe` no longer exists (dangling, inert;
  delete the shortcut).
- **cmd AutoRun**: empty in both hives.
- **PowerShell profiles**: stock oh-my-posh init, zoxide, conda shim, `ll`
  helpers, and your own `dl-master\scripts\dl.ps1` (no download-and-execute
  patterns). Nothing obfuscated or remote.
- **WMI**: only the default `SCM Event Log Consumer`.
- **All tasks with shell / script-host / user-writable-path actions**: every hit
  is an in-box Microsoft task under `\Microsoft\Windows\`, plus PowerToys,
  MEGAcmd, rclone. No task runs from Temp, ProgramData, or Public.
- **`\SoftLanding\<SID>\SoftLandingCreativeManagementTask`** (two, one per
  SID): COM-handler action, CLSID `{F576B2F9-...}` not registered in any hive,
  no author or source. This is the Windows 11 Start-menu "soft landing" task
  shipped in-box; with no registered class it cannot run and cannot open a
  console. Low concern; disable if you want it gone.
- **Local accounts**: `CodexSandboxOffline/Online`, `PerplexitySandbox` (your
  sandbox tools), `WsiAccount` (Windows Sandbox, disabled). No unexpected
  enabled account.

## What this does not cover

Services, drivers, browser extensions, Office add-ins, and the `\Microsoft\`
task tree beyond shell-action matches. Task Scheduler history is off, so
"what launched at 13:15" cannot be reconstructed after the fact; enable it if
you want that trail (`wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`).
