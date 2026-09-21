<#
.SYNOPSIS
  WaveEnergyHelper 앱 재시작 — 8501 을 잡고 있는 이 저장소의 streamlit 프로세스(래퍼 포함)를 모두 종료하고,
  포트가 빈 것을 확인한 뒤 `streamlit run main.py` 를 새 창에서 기동한다. 기동 후 위젯이 읽을 HEAD 와 현재 git HEAD 를 비교해 출력.

.DESCRIPTION
  배경: Windows 에서는 두 streamlit 이 같은 포트에 중복 바인드될 수 있어, 옛 프로세스를 죽이지 않고 "재시작"하면
  브라우저가 옛 프로세스(옛 코드)에 계속 붙는다(2026-09-22 사례). 이 스크립트는 종료 → 포트 확인 → 기동 순서를 강제한다.

  안전장치: 포트를 잡은 프로세스가 (a) 명령줄에 streamlit 이 없거나 (b) 이 저장소가 아닌 곳에서 뜬 streamlit 이면
  종료하지 않고 경고만 낸 뒤 종료 코드 2 로 끝난다(-Force 로 무시 가능). "이 저장소" 판정 = 명령줄에 저장소 절대경로가 있거나,
  프로세스의 현재 디렉터리(PEB 에서 읽음)가 저장소 루트다.

.PARAMETER Port      기본 8501.
.PARAMETER Force     저장소 판정에 실패해도(다른 저장소·경로 불명) streamlit 프로세스면 종료한다. streamlit 이 아닌 프로세스는 그래도 종료하지 않는다.
.PARAMETER NoLaunch  종료·포트 확인만 하고 기동하지 않는다.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\run_app.ps1
  바탕화면 바로가기: 대상 = powershell.exe -ExecutionPolicy Bypass -NoExit -File "C:\Users\user\Desktop\WaveEnergyHelper\scripts\run_app.ps1"
#>
[CmdletBinding()]
param(
    [int]$Port = 8501,
    [switch]$Force,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Continue"   # 네이티브 명령(git·python)의 stderr 가 종료 오류로 승격되지 않게 — 실패는 아래에서 값으로 검사
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path.TrimEnd("\")
$MainPy = Join-Path $Root "main.py"
if (-not (Test-Path $MainPy)) { Write-Host "main.py 없음: $MainPy" -ForegroundColor Red; exit 3 }

function Normalize-Dir([string]$p) {
    if (-not $p) { return $null }
    try { return (Resolve-Path $p -ErrorAction Stop).Path.TrimEnd("\").ToLowerInvariant() } catch { return $p.TrimEnd("\").ToLowerInvariant() }
}

# ---------------------------------------------------------------- 다른 프로세스의 현재 디렉터리 (PEB → RTL_USER_PROCESS_PARAMETERS.CurrentDirectory)
if (-not ("ProcCwd" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class ProcCwd {
    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_BASIC_INFORMATION { public IntPtr Reserved1; public IntPtr PebBaseAddress; public IntPtr Reserved2_0; public IntPtr Reserved2_1; public IntPtr UniqueProcessId; public IntPtr Reserved3; }
    [StructLayout(LayoutKind.Sequential)]
    struct UNICODE_STRING { public ushort Length; public ushort MaximumLength; public IntPtr Buffer; }
    [DllImport("ntdll.dll")] static extern int NtQueryInformationProcess(IntPtr h, int cls, ref PROCESS_BASIC_INFORMATION pbi, int len, out int ret);
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out IntPtr read);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    static IntPtr ReadPtr(IntPtr h, IntPtr addr) { byte[] b = new byte[IntPtr.Size]; IntPtr r; if (!ReadProcessMemory(h, addr, b, b.Length, out r)) return IntPtr.Zero; return IntPtr.Size == 8 ? (IntPtr)BitConverter.ToInt64(b, 0) : (IntPtr)BitConverter.ToInt32(b, 0); }
    public static string Get(int pid) {
        IntPtr h = OpenProcess(0x0010 | 0x0400, false, pid);   // VM_READ | QUERY_INFORMATION
        if (h == IntPtr.Zero) return null;
        try {
            PROCESS_BASIC_INFORMATION pbi = new PROCESS_BASIC_INFORMATION(); int ret;
            if (NtQueryInformationProcess(h, 0, ref pbi, Marshal.SizeOf(pbi), out ret) != 0) return null;
            int paramsOff = IntPtr.Size == 8 ? 0x20 : 0x10;     // PEB.ProcessParameters
            IntPtr pp = ReadPtr(h, (IntPtr)(pbi.PebBaseAddress.ToInt64() + paramsOff));
            if (pp == IntPtr.Zero) return null;
            int curDirOff = IntPtr.Size == 8 ? 0x38 : 0x24;     // RTL_USER_PROCESS_PARAMETERS.CurrentDirectory.DosPath (UNICODE_STRING)
            byte[] us = new byte[Marshal.SizeOf(typeof(UNICODE_STRING))]; IntPtr r;
            if (!ReadProcessMemory(h, (IntPtr)(pp.ToInt64() + curDirOff), us, us.Length, out r)) return null;
            ushort len = BitConverter.ToUInt16(us, 0);
            IntPtr buf = IntPtr.Size == 8 ? (IntPtr)BitConverter.ToInt64(us, 8) : (IntPtr)BitConverter.ToInt32(us, 4);
            if (buf == IntPtr.Zero || len == 0) return null;
            byte[] s = new byte[len];
            if (!ReadProcessMemory(h, buf, s, len, out r)) return null;
            return Encoding.Unicode.GetString(s);
        } finally { CloseHandle(h); }
    }
}
"@
}

function Get-Proc([int]$ProcId) { Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue }

function Test-OurStreamlit($proc) {
    # 반환: 'ours' | 'foreign-streamlit' | 'not-streamlit'
    $cmd = [string]$proc.CommandLine
    if ($cmd -notmatch "streamlit") { return "not-streamlit" }
    if ($cmd.ToLowerInvariant().Contains($Root.ToLowerInvariant())) { return "ours" }
    $cwd = $null
    try { $cwd = [ProcCwd]::Get([int]$proc.ProcessId) } catch { $cwd = $null }
    if ($cwd -and ((Normalize-Dir $cwd) -eq (Normalize-Dir $Root))) { return "ours" }
    return "foreign-streamlit"
}

function Get-Tree([int]$ProcId) {
    # 대상 + 부모(streamlit 래퍼일 때만) + 자식(전부). 중복 제거.
    $ids = New-Object System.Collections.Generic.List[int]
    $p = Get-Proc $ProcId
    if (-not $p) { return $ids }
    $ids.Add([int]$p.ProcessId)
    $parent = Get-Proc ([int]$p.ParentProcessId)
    if ($parent -and ([string]$parent.CommandLine) -match "streamlit") { $ids.Add([int]$parent.ProcessId) }
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcId" -ErrorAction SilentlyContinue | ForEach-Object { $ids.Add([int]$_.ProcessId) }
    return $ids | Select-Object -Unique
}

Write-Host "== WaveEnergyHelper 재시작 (포트 $Port) · 저장소 $Root"

# ---------------------------------------------------------------- 1. 포트 점유 프로세스 종료
$listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
if ($listeners.Count -eq 0) {
    Write-Host "포트 $Port 비어 있음 (종료할 프로세스 없음)"
} else {
    $blocked = $false
    foreach ($procId in $listeners) {
        $p = Get-Proc $procId
        if (-not $p) { continue }
        $kind = Test-OurStreamlit $p
        $started = if ($p.CreationDate) { ([datetime]$p.CreationDate).ToString("MM-dd HH:mm:ss") } else { "?" }
        $short = ([string]$p.CommandLine); if ($short.Length -gt 110) { $short = $short.Substring(0, 110) + "…" }
        $skip = $false
        if ($kind -eq "not-streamlit") {
            Write-Host "경고: 포트 $Port 를 streamlit 이 아닌 프로세스가 사용 중 — 종료하지 않음. pid $procId ($started) $short" -ForegroundColor Yellow
            $blocked = $true; $skip = $true
        } elseif ($kind -eq "foreign-streamlit") {
            if ($Force) {
                Write-Host "주의: 다른 저장소/경로의 streamlit 이지만 -Force 로 종료. pid $procId ($started) $short" -ForegroundColor Yellow
            } else {
                Write-Host "경고: 이 저장소가 아닌 streamlit 이 포트 $Port 사용 중 — 종료하지 않음(-Force 로 강제). pid $procId ($started) $short" -ForegroundColor Yellow
                $blocked = $true; $skip = $true
            }
        } else {
            Write-Host "이 저장소의 streamlit: pid $procId ($started) $short"
        }
        if ($skip) { continue }
        $tree = Get-Tree $procId
        foreach ($t in $tree) {
            if (-not (Get-Process -Id $t -ErrorAction SilentlyContinue)) { continue }   # 부모가 죽으며 함께 사라진 자식(conhost 등)
            try { Stop-Process -Id $t -Force -ErrorAction Stop; Write-Host "종료: pid $t" }
            catch { if (Get-Process -Id $t -ErrorAction SilentlyContinue) { Write-Host "종료 실패: pid $t — $($_.Exception.Message)" -ForegroundColor Yellow } else { Write-Host "종료(부모와 함께 사라짐): pid $t" } }
        }
    }
    if ($blocked) { Write-Host "포트 $Port 가 비지 않아 기동하지 않음." -ForegroundColor Red; exit 2 }
}

# ---------------------------------------------------------------- 2. 포트가 비었는지 확인 (최대 10초)
$free = $false
for ($i = 0; $i -lt 20; $i++) {
    if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) { $free = $true; break }
    Start-Sleep -Milliseconds 500
}
if (-not $free) { Write-Host "포트 $Port 가 10초 안에 비지 않음 — 기동 중단." -ForegroundColor Red; exit 2 }
Write-Host "포트 $Port 비어 있음 확인."
if ($NoLaunch) { exit 0 }

# ---------------------------------------------------------------- 3. 기동 (새 창, python -m streamlit — 래퍼 exe 없이 프로세스 1개)
$proc = Start-Process -FilePath "python" -ArgumentList @("-m", "streamlit", "run", "main.py", "--server.port", "$Port") `
    -WorkingDirectory $Root -PassThru
Write-Host "기동: pid $($proc.Id) · python -m streamlit run main.py --server.port $Port (cwd $Root)"

$up = $false
for ($i = 0; $i -lt 120; $i++) {
    $l = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($l -and ($l.OwningProcess -contains $proc.Id)) { $up = $true; break }
    if ($proc.HasExited) { break }
    Start-Sleep -Milliseconds 500
}
if (-not $up) { Write-Host "기동 실패 또는 60초 안에 포트 $Port Listen 없음 (pid $($proc.Id), exited=$($proc.HasExited))" -ForegroundColor Red; exit 4 }

# ---------------------------------------------------------------- 4. 위젯이 읽을 HEAD vs 현재 git HEAD
# 위젯(display/code_version)은 기동 시 `git rev-parse --short HEAD` 를 저장소 루트에서 한 번 캡처한다 — 같은 함수를 호출해 비교.
$widgetHead = (& python -c "import sys; sys.path.insert(0, r'$Root'); from display.code_version import capture_code_version; print(capture_code_version().head or '조회 불가')")
if (-not $widgetHead) { $widgetHead = "조회 불가" }
$gitNow = (& git -C $Root rev-parse --short HEAD); if (-not $gitNow) { $gitNow = "조회 불가" }
$match = if ($widgetHead -eq $gitNow) { "일치" } else { "불일치 — 기동 후 체크아웃이 바뀌었거나 git 조회 실패" }
Write-Host "위젯이 읽을 HEAD = $widgetHead · 현재 git HEAD = $gitNow → $match"
Write-Host "http://localhost:$Port/  (포트 소유 pid $($proc.Id))"
exit 0
