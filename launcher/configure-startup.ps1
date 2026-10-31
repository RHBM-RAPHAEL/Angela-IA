param(
    [switch]$Enable,
    [switch]$Disable,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
$display = [string][char]0x00C2 + 'ngela AI'
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot 'start-with-windows.ps1'
$exe = Join-Path $PSScriptRoot 'AngelaAI\bin\Release\net9.0\AngelaAI.exe'
$icon = Join-Path $PSScriptRoot 'assets\AngelaAI.ico'
$folder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $folder ($display + '.lnk')

if (($Enable -and $Disable) -or ($Status -and ($Enable -or $Disable))) {
    throw 'Use only -Enable, -Disable or -Status.'
}
if (-not ($Enable -or $Disable -or $Status)) {
    throw 'Specify -Enable, -Disable or -Status.'
}

if ($Disable) {
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force
    }
    Write-Output ('AUTOSTART_DISABLED: ' + $shortcutPath)
    exit 0
}

if ($Status) {
    if (Test-Path -LiteralPath $shortcutPath) {
        $shell = New-Object -ComObject WScript.Shell
        $existing = $shell.CreateShortcut($shortcutPath)
        Write-Output 'AUTOSTART_ENABLED'
        Write-Output ('LINK: ' + $shortcutPath)
        Write-Output ('TARGET: ' + $existing.TargetPath)
        Write-Output ('ARGUMENTS: ' + $existing.Arguments)
        exit 0
    }
    Write-Output 'AUTOSTART_DISABLED'
    exit 0
}

foreach ($required in @($script, $exe, $icon)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw ('Required launcher asset missing: ' + $required)
    }
}

if (-not (Test-Path -LiteralPath $folder -PathType Container)) {
    New-Item -Path $folder -ItemType Directory -Force | Out-Null
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $PSHOME 'powershell.exe'
$shortcut.Arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '"'
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = $icon + ',0'
$shortcut.Description = 'Angela AI - inicia na entrada do Windows com microfone ativo'
$shortcut.WindowStyle = 7
$shortcut.Save()

$check = $shell.CreateShortcut($shortcutPath)
if ($check.TargetPath -ne $shortcut.TargetPath -or
    $check.Arguments -notlike '*start-with-windows.ps1*') {
    throw 'Startup shortcut verification failed.'
}
Write-Output ('AUTOSTART_ENABLED: ' + $shortcutPath)
Write-Output ('TARGET: ' + $check.TargetPath)
Write-Output ('ARGUMENTS: ' + $check.Arguments)
