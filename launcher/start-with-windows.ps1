param([switch]$VerifyOnly)

# Autostart for Angela AI, current Windows user, no admin privileges.
# An interactive desktop session is required for the HUD and microphone.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $PSScriptRoot 'AngelaAI\bin\Release\net9.0\AngelaAI.exe'
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
$web = Join-Path $root 'angela\web'
$log = Join-Path $env:LOCALAPPDATA 'AngelaAI\logs\startup.log'
$uri = 'http://127.0.0.1:18766/'

function Write-StartupLog([string]$eventName) {
    try {
        $folder = Split-Path -Parent $log
        if (-not (Test-Path -LiteralPath $folder)) {
            New-Item -ItemType Directory -Path $folder -Force | Out-Null
        }
        $when = Get-Date -Format o
        Add-Content -LiteralPath $log -Value ($when + ' ' + $eventName) -Encoding UTF8
    } catch {
        # Logging cannot prevent startup.
    }
}

function Test-HudReady {
    try {
        $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
        return ([int]$response.StatusCode -eq 200 -and
                [string]$response.Content -match 'id="scene"')
    } catch {
        return $false
    }
}

try {
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw 'Branded AngelaAI.exe not found.'
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'Python 3.12 not found.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $web 'index.html') -PathType Leaf)) {
        throw 'Angela HUD web assets not found.'
    }

    if ($VerifyOnly) {
        Write-Output 'STARTUP_PREREQUISITES_OK'
        exit 0
    }

    # Avoid two instances/microphone grabs on login or shortcut double-click.
    if (Get-Process -Name AngelaAI -ErrorAction SilentlyContinue) {
        Write-StartupLog 'ALREADY_RUNNING'
        Write-Output 'ALREADY_RUNNING'
        exit 0
    }

    # The hologram page uses a local-only, loopback HTTP server. Normally
    # it was started manually and would disappear after a Windows reboot.
    if (-not (Test-HudReady)) {
        $hudProcess = Start-Process -FilePath $python -ArgumentList @('-m', 'http.server', '18766', '--bind', '127.0.0.1') -WorkingDirectory $web -WindowStyle Hidden -PassThru
        Write-StartupLog ('HUD_START_REQUESTED pid=' + $hudProcess.Id)
        $ready = $false
        for ($i = 0; $i -lt 12; $i++) {
            Start-Sleep -Milliseconds 250
            if (Test-HudReady) {
                $ready = $true
                break
            }
            if ($hudProcess.HasExited) { break }
        }
        if (-not $ready) {
            throw 'Local hologram server did not become ready.'
        }
    }

    # Enable voice for this Angela process only (no system-wide changes).
    $env:ANGELA_ENABLE_VOICE = '1'
    $env:ANGELA_START_ON_LOGIN = '1'
    $app = Start-Process -FilePath $exe -WorkingDirectory $root -PassThru
    Write-StartupLog ('ANGELA_STARTED pid=' + $app.Id + ' mic=enabled')
    Write-Output ('ANGELA_STARTED_PID=' + $app.Id)
    exit 0
} catch {
    Write-StartupLog ('ERROR ' + $_.Exception.GetType().Name + ': ' +
                      $_.Exception.Message)
    Write-Error $_.Exception.Message
    exit 1
}
