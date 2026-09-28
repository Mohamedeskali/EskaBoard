<#
Install, update or uninstall EskaBoard on Windows 10/11 for the current user.

  powershell -ExecutionPolicy Bypass -File .\install.ps1              install or update, then start it
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall   remove shortcuts, settings, venv and this folder

Works from the folder it is in: an extracted ZIP, or %LOCALAPPDATA%\EskaBoard
when get.ps1 runs it. Needs no administrator rights. Installs Python with winget
if it is missing. Never changes the firewall or the network type: it only warns.
Keep this file ASCII: Windows PowerShell 5.1 reads scripts without a BOM as ANSI.
#>
param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'

$Root = $PSScriptRoot
$Venv = Join-Path $Root 'venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$VenvPythonw = Join-Path $Venv 'Scripts\pythonw.exe'
$Icon = Join-Path $Root 'assets\eskaboard.ico'
$ConfigDir = Join-Path $env:APPDATA 'EskaBoard'   # log and status page address (phonekb/webgui.py)
$StartMenuLink = Join-Path ([Environment]::GetFolderPath('Programs')) 'EskaBoard.lnk'
$DesktopLink = Join-Path ([Environment]::GetFolderPath('Desktop')) 'EskaBoard.lnk'
$MinPython = [version]'3.8'
$WingetPython = 'Python.Python.3.13'
$PythonOrg = 'https://www.python.org/downloads/windows/'

function Say([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
function Warn([string]$Text) { Write-Host "Warning: $Text" -ForegroundColor Yellow }
function Fail([string]$Text) { Write-Host "Error: $Text" -ForegroundColor Red; exit 1 }

# Runs a program and returns its exit code. Its error output stays plain text
# (Windows PowerShell 5.1 can turn it into errors that stop the script).
function Invoke-Program([string]$Exe, [string[]]$Arguments, [switch]$Quiet) {
    $ErrorActionPreference = 'Continue'
    if ($Quiet) { & $Exe @Arguments *> $null } else { & $Exe @Arguments | Out-Host }
    return $LASTEXITCODE
}

function Test-Under([string]$Path, [string]$Dir) {
    return [bool]$Path -and $Path.StartsWith($Dir.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
}

# ---- running copies ----

# EskaBoard processes; with -Dir, only the ones started from that folder: the venv
# launcher (venv\Scripts\pythonw.exe) and the Python it starts, which has the
# same "-m phonekb" command line.
function Get-EskaBoardProcesses([string]$Dir) {
    $all = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -match '-m\s+phonekb' })
    if (-not $Dir) { return $all }
    $ids = @($all | Where-Object { Test-Under $_.ExecutablePath $Dir } | ForEach-Object { $_.ProcessId })
    return @($all | Where-Object { $ids -contains $_.ProcessId -or $ids -contains $_.ParentProcessId })
}

function Stop-EskaBoard([string]$Dir) {
    $procs = @(Get-EskaBoardProcesses $Dir)
    if ($procs.Count -eq 0) { return }
    Say 'Stopping the running EskaBoard'
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($p in $procs) { Wait-Process -Id $p.ProcessId -Timeout 10 -ErrorAction SilentlyContinue }
}

# ---- Python ----

function Get-PythonInfo([string]$Exe, [string[]]$Pre = @()) {
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Exe @Pre -c "import sys; print('%d.%d %s' % (sys.version_info[0], sys.version_info[1], sys.executable))" 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    if ("$(@($out)[-1])".Trim() -notmatch '^(\d+\.\d+) (.+)$') { return $null }
    return [pscustomobject]@{ Version = [version]$Matches[1]; Path = $Matches[2] }
}

# Newest usable Python: the py launcher, python on PATH (skipping the Microsoft
# Store stub, which prints nothing), then per-user python.org installs.
function Find-Python {
    $tries = @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $tries += , @('py', '-3') }
    foreach ($name in 'python', 'python3') {
        $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $tries += , @($cmd.Source) }
    }
    $userInstalls = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    foreach ($dir in @(Get-ChildItem $userInstalls -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending)) {
        $tries += , @((Join-Path $dir.FullName 'python.exe'))
    }
    $script:OldPython = $null
    foreach ($t in $tries) {
        $info = Get-PythonInfo $t[0] @($t | Select-Object -Skip 1)
        if (-not $info) { continue }
        if ($info.Version -ge $MinPython) { return $info }
        $script:OldPython = $info
    }
    return $null
}

function Install-Python {
    $why = if ($script:OldPython) { "Python $($script:OldPython.Version) is too old" } else { 'Python was not found' }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "$why; EskaBoard needs Python $MinPython or newer.
    Install it from $PythonOrg
    (tick 'Add python.exe to PATH' in the installer), then run this again."
    }
    Say "$why. Installing Python with winget (for this user only)"
    $code = Invoke-Program winget @('install', '--id', $WingetPython, '--exact', '--scope', 'user', '--silent',
        '--accept-package-agreements', '--accept-source-agreements')
    if ($code -ne 0) {
        Fail "winget could not install Python (exit code $code).
    Install it from $PythonOrg
    (tick 'Add python.exe to PATH' in the installer), then run this again."
    }
    # winget changed PATH for new windows; take it into this one too
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
}

# ---- shortcuts ----

function Get-ShortcutTarget([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return (New-Object -ComObject WScript.Shell).CreateShortcut($Path).TargetPath
}

function New-Shortcut([string]$Path) {
    $link = (New-Object -ComObject WScript.Shell).CreateShortcut($Path)
    $link.TargetPath = $VenvPythonw
    $link.Arguments = '-m phonekb --gui'
    $link.WorkingDirectory = $Root
    if (Test-Path -LiteralPath $Icon) { $link.IconLocation = "$Icon,0" }
    $link.Description = 'Use your phone as a keyboard for this PC'
    $link.Save()
}

# ---- network (read only) ----

function Show-NetworkWarnings([string]$BasePython) {
    try {
        $public = @(Get-NetConnectionProfile -ErrorAction Stop | Where-Object { "$($_.NetworkCategory)" -eq 'Public' })
    } catch {
        $public = @()
    }
    foreach ($p in $public) {
        Warn "the network '$($p.Name)' ($($p.InterfaceAlias)) is set to Public."
    }
    if ($public.Count) {
        Write-Host "    Windows blocks the phone on a Public network. If this is your home or office"
        Write-Host "    Wi-Fi, make it Private:"
        Write-Host "      Settings > Network & internet > Wi-Fi (or Ethernet) > your network >"
        Write-Host "      Network profile type > Private"
        Write-Host "    EskaBoard does not change the network type or the firewall for you."
    }

    # Inbound block rules for this Python on Private networks: usually "Cancel"
    # was clicked when Windows Firewall asked about Python.
    if (-not $BasePython) { return }
    $programs = @($BasePython, (Join-Path (Split-Path $BasePython) 'pythonw.exe'))
    try {
        $blocking = @(Get-NetFirewallApplicationFilter -ErrorAction Stop |
            Where-Object { $programs -contains $_.Program } |
            Get-NetFirewallRule -ErrorAction Stop |
            Where-Object { "$($_.Direction)" -eq 'Inbound' -and "$($_.Action)" -eq 'Block' -and "$($_.Enabled)" -eq 'True' -and
                           ("$($_.Profile)" -match 'Private|Any') })
    } catch {
        return
    }
    if ($blocking.Count) {
        Warn 'Windows Firewall has a rule that blocks Python on Private networks, so the phone cannot connect.'
        Write-Host "    To allow it: Start > 'Allow an app through Windows Firewall' > Change settings >"
        Write-Host "    tick 'Private' next to every 'Python' entry > OK. (Needs an administrator.)"
        Write-Host "    Blocking rule(s): $(($blocking | ForEach-Object { $_.DisplayName } | Select-Object -Unique) -join ', ')"
    }
}

# ---- uninstall ----

function Remove-Tree([string]$Path) {
    for ($i = 1; $i -le 3; $i++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return $true
        } catch {
            if ($i -eq 3) { Warn "could not remove ${Path}: $($_.Exception.Message)"; return $false }
            Start-Sleep -Seconds 1
        }
    }
}

function Uninstall-EskaBoard {
    $profileDir = [Environment]::GetFolderPath('UserProfile').TrimEnd('\')
    if (-not (Test-Path (Join-Path $Root 'phonekb\__main__.py')) -or $Root.TrimEnd('\') -eq $profileDir -or
        $Root.TrimEnd('\') -eq ([IO.Path]::GetPathRoot($Root)).TrimEnd('\')) {
        Fail "$Root does not look like an EskaBoard folder; not removing it."
    }

    Stop-EskaBoard $Root
    $removed = @()
    foreach ($link in $StartMenuLink, $DesktopLink) {
        $target = Get-ShortcutTarget $link
        if (-not $target) { continue }
        if (Test-Under $target $Root) {
            Remove-Item -LiteralPath $link -Force
            $removed += "shortcut   $link"
        } else {
            Say "Keeping $link : it opens an EskaBoard in another folder ($target)."
        }
    }
    if ((Test-Path -LiteralPath $ConfigDir) -and (Remove-Tree $ConfigDir)) {
        $removed += "settings   $ConfigDir (log and status page address)"
    }

    # A folder cannot be removed while this window is in it
    $parent = Split-Path $Root -Parent
    Set-Location -LiteralPath $parent
    [Environment]::CurrentDirectory = $parent
    if (Remove-Tree $Root) {
        $removed += "program    $Root (with its venv)"
    } else {
        Write-Host "    Close any window that uses $Root, then delete the folder by hand."
    }

    Say 'EskaBoard is uninstalled. Removed:'
    if ($removed.Count) { $removed | ForEach-Object { Write-Host "    $_" } } else { Write-Host '    nothing' }
    Write-Host '    Left in place: Python itself, and any firewall rule Windows made for Python'
    Write-Host "    (Start > 'Allow an app through Windows Firewall' lists it)."
}

# ---- install ----

function Install-EskaBoard {
    if ([Environment]::OSVersion.Version.Major -lt 10) {
        Warn 'EskaBoard is made for Windows 10 and 11.'
    }
    foreach ($f in 'phonekb\__main__.py', 'requirements.txt') {
        if (-not (Test-Path (Join-Path $Root $f))) { Fail "$Root\$f is missing. Extract the whole ZIP and run install.ps1 from it." }
    }

    # Running files can't be replaced: stop a copy started from this folder
    Stop-EskaBoard $Root

    $python = Find-Python
    if (-not $python) {
        Install-Python
        $python = Find-Python
        if (-not $python) { Fail 'Python was installed but cannot be found yet. Open a new PowerShell window and run this again.' }
    }
    Say "Using Python $($python.Version) ($($python.Path))"

    # (Re)create the venv if it is missing or broken, e.g. after Python was upgraded
    $pipOk = (Test-Path $VenvPython) -and ((Invoke-Program $VenvPython @('-m', 'pip', '--version') -Quiet) -eq 0)
    if (-not $pipOk) {
        if (Test-Path $Venv) { [void](Remove-Tree $Venv) }
        Say "Creating venv in $Venv"
        if ((Invoke-Program $python.Path @('-m', 'venv', $Venv)) -ne 0) { Fail 'could not create the venv.' }
    }
    Say 'Installing Python packages'
    $code = Invoke-Program $VenvPython @('-m', 'pip', 'install', '--disable-pip-version-check', '--quiet',
        '-r', (Join-Path $Root 'requirements.txt'))
    if ($code -ne 0) { Fail 'pip could not install the packages (no internet?). See the messages above.' }
    if ((Invoke-Program $VenvPython @('-c', 'import aiohttp, nacl, qrcode, PIL')) -ne 0) {
        Fail 'the venv cannot import the Python packages. See the messages above.'
    }

    Say 'Adding EskaBoard to the Start menu and the desktop'
    New-Shortcut $StartMenuLink
    New-Shortcut $DesktopLink

    Show-NetworkWarnings $python.Path

    # Only one copy runs at a time; starting this one would show the other's page
    $others = @(Get-EskaBoardProcesses | Where-Object { -not (Test-Under $_.ExecutablePath $Root) })
    if ($others.Count) {
        Write-Host '    Note: another EskaBoard is already running. Stop it (red button on its page),'
        Write-Host '    then open EskaBoard from the Start menu.'
    }

    Say 'Starting EskaBoard: its page opens in your browser'
    Start-Process -FilePath $VenvPythonw -ArgumentList '-m', 'phonekb', '--gui' -WorkingDirectory $Root
    Write-Host '    The first time, Windows Firewall may ask about Python: tick Private networks'
    Write-Host '    and click Allow, or the phone cannot connect.'
    Write-Host '    Open it later from the Start menu or the desktop shortcut.'
}

if ($Uninstall) { Uninstall-EskaBoard } else { Install-EskaBoard }
