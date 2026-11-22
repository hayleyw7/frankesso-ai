$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$setup = Join-Path $root 'dist/Frankesso-2.0.0-Windows-x64-Setup.exe'
$expected = ((Get-Content -LiteralPath (Join-Path $root 'dist/SHA256SUMS.txt') -Raw).Trim() -split '\s+')[0]
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $setup).Hash -ne $expected) { throw 'Setup checksum mismatch.' }

function Run-Installer($exe) {
    $p = Start-Process -FilePath $exe -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Installer or uninstaller exit code $($p.ExitCode)." }
}
$app = Join-Path $env:LOCALAPPDATA 'Programs/Frankesso'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'Frankesso.lnk'
$model = Join-Path $env:LOCALAPPDATA 'FrankessoDesktop/models/Qwen3-4B-Q4_K_M.gguf'
if ((Test-Path $app) -or (Test-Path $shortcutPath) -or (Test-Path $model)) {
    throw 'Expected a clean Windows user profile.'
}
Run-Installer $setup
try {
    $launcher = Join-Path $app 'python/pythonw.exe'
    $icon = Join-Path $app 'assets/frankesso.ico'
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
    if (-not (Test-Path $shortcutPath) -or $lnk.TargetPath -ne $launcher -or
        $lnk.IconLocation -ne ($icon + ',0') -or $lnk.Arguments -notmatch '--installed') {
        throw 'The current-user Start shortcut did not point to the bundled app and artwork.'
    }
    foreach ($license in @('python.txt','llama.cpp.txt','qwen.txt')) {
        if (-not (Test-Path (Join-Path $app "licenses/$license"))) { throw "Missing notice: $license" }
    }
    $env:SMOKE_APP_ROOT = $app
    & (Join-Path $app 'python/python.exe') -E -s -B (Join-Path $PSScriptRoot 'smoke_installed.py')
    if ($LASTEXITCODE -ne 0) { throw 'Installed-app smoke test failed.' }
} finally {
    Run-Installer (Join-Path $app 'unins000.exe')
}
if ((Test-Path $shortcutPath) -or (Test-Path $model) -or (Test-Path (Join-Path $app 'agent/desktop.py'))) {
    throw 'Uninstall left app files, Start shortcut, or the model behind.'
}
