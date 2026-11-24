$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'dist'
$setupName = 'Frankesso-2.0.0-Windows-x64-Setup.exe'
$setup = Join-Path $dist $setupName
$verified = @{}
foreach ($line in Get-Content -LiteralPath (Join-Path $dist 'SHA256SUMS.txt')) {
    if ($line -notmatch '^([0-9a-f]{64})  (Frankesso-2\.0\.0-Windows-x64-Setup(?:\.exe|-\d+[a-z]*\.bin))$') {
        throw 'Unexpected checksum entry.'
    }
    $hash, $name = $Matches[1], $Matches[2]
    if ($verified.ContainsKey($name)) { throw "Duplicate checksum entry: $name" }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $dist $name)).Hash -ne $hash) {
        throw "Package checksum mismatch: $name"
    }
    $verified[$name] = $true
}
$slices = @(Get-ChildItem -LiteralPath $dist -Filter 'Frankesso-2.0.0-Windows-x64-Setup-*.bin' -File)
if (-not $verified.ContainsKey($setupName) -or $slices.Count -lt 2 -or $verified.Count -ne (1 + $slices.Count)) {
    throw 'Missing installer data files or checksums.'
}

function Run-Installer($exe) {
    $p = Start-Process -FilePath $exe -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Installer or uninstaller exit code $($p.ExitCode)." }
}
$app = Join-Path $env:LOCALAPPDATA 'Programs/Frankesso'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'Frankesso.lnk'
$model = Join-Path $app 'models/Qwen3-4B-Q4_K_M.gguf'
$legacyModel = Join-Path $env:LOCALAPPDATA 'FrankessoDesktop/models/Qwen3-4B-Q4_K_M.gguf'
if ((Test-Path $app) -or (Test-Path $shortcutPath) -or (Test-Path $model) -or (Test-Path $legacyModel)) {
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
    $expectedModel = '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'
    if ((Get-Item -LiteralPath $model).Length -ne 2497280256 -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $model).Hash -ne $expectedModel) {
        throw 'The installed package did not provide the exact bundled model.'
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
