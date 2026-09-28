<#
One-line install / update of EskaBoard on Windows 10/11, in PowerShell:
  irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1 | iex
Run it again to update. To uninstall:
  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1))) -Uninstall

Downloads the project ZIP to %LOCALAPPDATA%\EskaBoard (or $env:ESKABOARD_DIR),
replacing the program files but keeping the venv, then runs install.ps1 from
there. $env:ESKABOARD_ZIP may name another ZIP, as a URL or a local file.
Needs no administrator rights. Keep this file ASCII (Windows PowerShell 5.1).
#>
param([switch]$Uninstall)

# Everything runs inside this function: "irm | iex" runs in the caller's
# session, so the script must not change its settings or call exit.
function Invoke-EskaBoardGet([switch]$Uninstall) {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is very slow with it
    $zipUrl = if ($env:ESKABOARD_ZIP) { $env:ESKABOARD_ZIP } else { 'https://github.com/Mohamedeskali/EskaBoard/archive/refs/heads/main.zip' }
    $dir = if ($env:ESKABOARD_DIR) { $env:ESKABOARD_DIR } else { Join-Path $env:LOCALAPPDATA 'EskaBoard' }
    $dir = [IO.Path]::GetFullPath($dir).TrimEnd('\')
    $configDir = Join-Path $env:APPDATA 'EskaBoard'
    $getUrl = 'https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1'

    function Say([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }
    function Test-Under([string]$Path, [string]$Dir) {
        return [bool]$Path -and $Path.StartsWith($Dir + '\', [StringComparison]::OrdinalIgnoreCase)
    }
    function Get-Version([string]$Dir) {
        $init = Join-Path $Dir 'phonekb\__init__.py'
        if ((Test-Path -LiteralPath $init) -and ((Get-Content -LiteralPath $init -Raw) -match '__version__\s*=\s*"([^"]+)"')) { return $Matches[1] }
        return $null
    }
    # Runs install.ps1 in a new PowerShell (execution policy allowed for that run only)
    function Invoke-Installer([string]$Extra) {
        $installer = Join-Path $dir 'install.ps1'
        $exe = (Get-Process -Id $PID).Path
        $p = Start-Process -FilePath $exe -NoNewWindow -Wait -PassThru `
            -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$installer`" $Extra"
        return $p.ExitCode
    }
    # Same as Stop-EskaBoard in install.ps1: the venv launcher and its child Python
    function Stop-EskaBoard {
        $all = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
            Where-Object { $_.CommandLine -match '-m\s+phonekb' })
        $ids = @($all | Where-Object { Test-Under $_.ExecutablePath $dir } | ForEach-Object { $_.ProcessId })
        $procs = @($all | Where-Object { $ids -contains $_.ProcessId -or $ids -contains $_.ParentProcessId })
        if ($procs.Count -eq 0) { return }
        Say 'Stopping the running EskaBoard to update it'
        foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
        foreach ($p in $procs) { Wait-Process -Id $p.ProcessId -Timeout 10 -ErrorAction SilentlyContinue }
    }

    $isEskaBoard = Test-Path -LiteralPath (Join-Path $dir 'phonekb\__main__.py')

    if ($Uninstall) {
        if ($isEskaBoard -and (Test-Path -LiteralPath (Join-Path $dir 'install.ps1'))) {
            if ((Invoke-Installer '-Uninstall') -ne 0) { throw 'uninstalling failed; see the messages above.' }
            return
        }
        Say "EskaBoard is not installed in $dir. Removing what is left of it"
        foreach ($folder in 'Programs', 'Desktop') {
            $base = [Environment]::GetFolderPath($folder)
            $link = if ($base) { Join-Path $base 'EskaBoard.lnk' } else { '' }
            if (-not $link -or -not (Test-Path -LiteralPath $link)) { continue }
            $target = (New-Object -ComObject WScript.Shell).CreateShortcut($link).TargetPath
            if (Test-Under $target $dir) {
                Remove-Item -LiteralPath $link -Force
                Write-Host "    Removed shortcut $link"
            }
        }
        if (Test-Path -LiteralPath $configDir) {
            Remove-Item -LiteralPath $configDir -Recurse -Force
            Write-Host "    Removed settings $configDir"
        }
        return
    }

    if ((Test-Path -LiteralPath $dir) -and -not $isEskaBoard -and @(Get-ChildItem -LiteralPath $dir -Force).Count) {
        throw "$dir exists but is not EskaBoard. Move it away (or set `$env:ESKABOARD_DIR) and run this again."
    }

    # Download and unpack first: a failed download leaves the installed copy running
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('EskaBoard-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        $zipFile = Join-Path $tmp 'EskaBoard.zip'
        if ($zipUrl -match '^https?://') {
            Say "Downloading $zipUrl"
            # Older Windows 10 builds do not offer TLS 1.2 by default; GitHub needs it
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            try {
                Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
            } catch {
                throw "could not download $zipUrl ($($_.Exception.Message)). Check the internet connection."
            }
        } else {
            Say "Using $zipUrl"
            Copy-Item -LiteralPath $zipUrl -Destination $zipFile
        }
        $unpacked = Join-Path $tmp 'unpacked'
        Expand-Archive -LiteralPath $zipFile -DestinationPath $unpacked
        # GitHub ZIPs hold one folder (EskaBoard-main); a hand-made one may not
        $src = @(@(Get-Item -LiteralPath $unpacked) + @(Get-ChildItem -LiteralPath $unpacked -Directory)) |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'phonekb\__main__.py') } |
            Select-Object -First 1
        if (-not $src) { throw "the ZIP does not contain EskaBoard (no phonekb\__main__.py)." }

        $old = Get-Version $dir
        $new = Get-Version $src.FullName
        if ($old) {
            Stop-EskaBoard
            if ($old -eq $new) { Say "Reinstalling EskaBoard $new in $dir (already the latest)" }
            else { Say "Updating EskaBoard $old -> $new in $dir" }
            # Replace the program files; keep the venv so packages are not downloaded again
            Get-ChildItem -LiteralPath $dir -Force | Where-Object { $_.Name -ne 'venv' } | Remove-Item -Recurse -Force
        } else {
            Say "Installing EskaBoard $new in $dir"
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        Get-ChildItem -LiteralPath $src.FullName -Force | Copy-Item -Destination $dir -Recurse -Force
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    if ((Invoke-Installer '') -ne 0) { throw 'the installer failed; see the messages above.' }
    Say 'Done.'
    Write-Host '    Update it:    run the same command again.'
    Write-Host '    Uninstall it: run this in PowerShell:'
    Write-Host "      & ([scriptblock]::Create((irm $getUrl))) -Uninstall"
}

try {
    Invoke-EskaBoardGet -Uninstall:$Uninstall
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
