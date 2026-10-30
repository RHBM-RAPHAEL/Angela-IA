param([switch]$CreateDesktopShortcut)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $PSScriptRoot 'AngelaAI\AngelaAI.csproj'
$exe = Join-Path $PSScriptRoot 'AngelaAI\bin\Release\net9.0\AngelaAI.exe'
$display = [string][char]0x00C2 + 'ngela AI'

& dotnet build $project -c Release --verbosity quiet
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $exe)) {
    throw 'Failed to build AngelaAI executable.'
}

$description = (Get-Item -LiteralPath $exe).VersionInfo.FileDescription
if ($description -ne $display) {
    throw "Incorrect Windows FileDescription: $description"
}

if ($CreateDesktopShortcut) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $target = Join-Path $desktop ($display + '.lnk')
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($target)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = $display + ' - Assistente pessoal com voz e visao'
    $shortcut.Save()
    Write-Output ('SHORTCUT_READY: ' + $target)
}
Write-Output ('LAUNCHER_READY: ' + $exe)
