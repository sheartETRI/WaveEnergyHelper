# 추적 주기 실행 등록 — 일 1회 09:30 (로컬/KST).
#
# 1d 봉 마감이 09:00 KST 이므로 그 이후에 돈다.
# "놓친 실행 즉시 시작"(StartWhenAvailable)을 켜서 PC 가 꺼져 있던 날도 다음 부팅에
# 한 번 따라잡는다. schtasks /Create /XML 로 등록한다 —
# StartWhenAvailable 은 schtasks 평문 플래그로는 설정할 수 없어 XML 을 쓴다.
#
# 실행: powershell -ExecutionPolicy Bypass -File scripts\register_daily_tracking.ps1
# 해제: schtasks /Delete /TN "WaveEnergyHelper Daily Tracking" /F

param(
    [string]$TaskName = "WaveEnergyHelper Daily Tracking",
    [string]$StartTime = "09:30:00"
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repo "scripts\daily_tracking.py"
if (-not (Test-Path $script)) { throw "not found: $script" }

$python = (Get-Command python).Source
$startBoundary = (Get-Date -Format "yyyy-MM-dd") + "T" + $StartTime

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>WaveEnergyHelper 추적 주기 실행 — 기록 전용. 판정·알림·자동 매매 없음.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$python</Command>
      <Arguments>"$script"</Arguments>
      <WorkingDirectory>$repo</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$tmp = Join-Path $env:TEMP "wave_daily_tracking_task.xml"
[System.IO.File]::WriteAllText($tmp, $xml, [System.Text.Encoding]::Unicode)

schtasks /Create /TN "$TaskName" /XML "$tmp" /F
Remove-Item $tmp -Force

Write-Output "registered: $TaskName ($StartTime daily, StartWhenAvailable=true)"
schtasks /Query /TN "$TaskName" /FO LIST
