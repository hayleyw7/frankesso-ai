# Build-only script: the generated installer never runs these developer tools.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $PSScriptRoot 'build'
if (Test-Path $build) { throw "Build staging already exists: $build. Move it aside to build again." }
$payload = Join-Path $build 'payload'
$python = Join-Path $payload 'python'
$third = Join-Path $payload 'licenses'
$runner = Join-Path $payload 'runner'
$models = Join-Path $build 'models'
New-Item -ItemType Directory -Path $build,$payload,$third,$runner,$models | Out-Null

function Run-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE." }
}
function Install-BuildTool {
    param([string]$Executable, [string[]]$Arguments)
    $run = Start-Process -FilePath $Executable -ArgumentList $Arguments -Wait -PassThru
    if ($run.ExitCode -ne 0) { throw "$Executable failed with exit code $($run.ExitCode)." }
}
function Download-Pinned {
    param([string]$Url, [string]$Path, [string]$Sha256)
    Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash -ne $Sha256) {
        throw "Digest mismatch for $Path."
    }
}

# Python.org Windows amd64 installer. Stage a private copy on the build runner only.
# https://www.python.org/downloads/release/python-31316/
$pythonSetup = Join-Path $build 'python-3.13.16-amd64.exe'
Download-Pinned 'https://www.python.org/ftp/python/3.13.16/python-3.13.16-amd64.exe' `
    $pythonSetup 'fb4f9f5d438b2396da0086dc70b935c530cb578e37adc6d354f7ad2037fee83b'
Install-BuildTool $pythonSetup @('/quiet', 'InstallAllUsers=0', ('TargetDir="' + $python + '"'),
    'PrependPath=0', 'AppendPath=0', 'AssociateFiles=0', 'Shortcuts=0', 'Include_launcher=0',
    'Include_doc=0', 'Include_dev=0', 'Include_test=0', 'Include_tools=0', 'Include_pip=0',
    'Include_tcltk=1', 'Include_debug=0', 'Include_symbols=0', 'CompileAll=0')
Copy-Item (Join-Path $python 'LICENSE.txt') (Join-Path $third 'python.txt')
Run-Checked (Join-Path $python 'python.exe') @('-E','-s','-B','-c','import sys, ssl, tkinter; assert sys.version_info[:3] == (3,13,16); print(tkinter.TkVersion)')
if (-not (Test-Path (Join-Path $python 'pythonw.exe'))) { throw 'The bundled windowed interpreter is missing.' }

# Build the upstream llama.cpp source with a static C++ runtime and no web UI.
# The immutable commit is the subject of upstream attestation 59465966 (b11865).
$llamaCommit = '78a8ae14be559b45f5f13ddee82c188b683d5d8d'
$llama = Join-Path $build 'llama'
$llamaOut = Join-Path $build 'llama-out'
Run-Checked git @('init',$llama)
Run-Checked git @('-C',$llama,'fetch','--depth=1','https://github.com/ggml-org/llama.cpp.git',$llamaCommit)
Run-Checked git @('-C',$llama,'checkout','--detach','FETCH_HEAD')
if ((& git -C $llama rev-parse HEAD) -ne $llamaCommit) { throw 'llama.cpp revision mismatch.' }
Run-Checked cmake @('-S',$llama,'-B',$llamaOut,'-G','Visual Studio 17 2022','-A','x64',
    '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded','-DBUILD_SHARED_LIBS=OFF','-DGGML_BACKEND_DL=OFF',
    '-DGGML_OPENMP=OFF','-DGGML_NATIVE=OFF','-DGGML_SSE42=ON','-DGGML_AVX=ON',
    '-DGGML_AVX2=ON','-DGGML_BMI2=OFF','-DLLAMA_OPENSSL=OFF','-DLLAMA_BUILD_TESTS=OFF',
    '-DLLAMA_BUILD_EXAMPLES=OFF','-DLLAMA_BUILD_UI=OFF','-DLLAMA_USE_PREBUILT_UI=OFF',
    '-DGGML_RPC=OFF','-DLLAMA_CONNECT=OFF','-DLLAMA_BUILD_APP=OFF','-DLLAMA_BUILD_SERVER=ON')
Run-Checked cmake @('--build',$llamaOut,'--config','Release','--target','llama-server','--parallel','4')
$binary = @(Get-ChildItem -Path $llamaOut -Filter 'llama-server.exe' -File -Recurse)
if ($binary.Count -ne 1) { throw 'Expected exactly one Windows llama-server executable.' }
Copy-Item $binary[0].FullName $runner
Copy-Item (Join-Path $llama 'LICENSE') (Join-Path $third 'llama.cpp.txt')
if (Test-Path (Join-Path $llama 'licenses')) {
    Copy-Item (Join-Path $llama 'licenses') (Join-Path $third 'llama-upstream') -Recurse
}
$llamaExe = Join-Path $runner 'llama-server.exe'
$help = & $llamaExe '--help' 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw 'The bundled runtime could not start.' }
foreach ($flag in @('--offline','--no-agent','--no-ui-mcp-proxy','--no-ui','--no-op-offload','--reasoning','--no-warmup')) {
    if (-not $help.Contains($flag)) { throw "The bundled runtime lacked required flag $flag." }
}

# Pin and bundle the model at build time. Setup and the installed app never fetch it.
$modelUrl = 'https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf'
$modelPath = Join-Path $models 'Qwen3-4B-Q4_K_M.gguf'
$modelHash = '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'
Run-Checked curl.exe @('--fail','--location','--retry','3','--max-time','600','--silent','--show-error',
    $modelUrl,'--output',$modelPath)
if ((Get-Item -LiteralPath $modelPath).Length -ne 2497280256 -or
    (Get-FileHash -Algorithm SHA256 -LiteralPath $modelPath).Hash -ne $modelHash) {
    throw 'The bundled model size or SHA-256 is incorrect.'
}

# Preserve the license from the exact Qwen quantization included in the installer.
Invoke-WebRequest -UseBasicParsing `
    -Uri 'https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/LICENSE' `
    -OutFile (Join-Path $third 'qwen.txt')
$pyFiles = @('agent.py','desktop.py','run_agent.py','model_setup.py','document_readers.py','private_skills.py','local_only.py','chat_state.py')
$appAgent = Join-Path $payload 'agent'
New-Item -ItemType Directory -Path $appAgent | Out-Null
foreach ($file in $pyFiles) { Copy-Item (Join-Path $root "agent/$file") $appAgent }
Copy-Item (Join-Path $root 'assets') $payload -Recurse
Copy-Item (Join-Path $root 'LICENSE') $payload
Copy-Item (Join-Path $root 'THIRD_PARTY_NOTICES.md') $payload

# Compiler is needed on the builder only. Immutable upstream version and valid publisher signature.
$innoSetup = Join-Path $build 'innosetup-6.7.4.exe'
Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe' -OutFile $innoSetup
$sig = Get-AuthenticodeSignature -FilePath $innoSetup
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.GetNameInfo('SimpleName',$false) -ne 'Pyrsys B.V.') {
    throw 'The compiler installer is not signed by its official publisher.'
}
$compilerRoot = Join-Path $build 'inno'
Install-BuildTool $innoSetup @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/PORTABLE=1',('/DIR="' + $compilerRoot + '"'))
$compiler = Join-Path $compilerRoot 'ISCC.exe'
Run-Checked $compiler @((Join-Path $PSScriptRoot 'Frankesso.iss'))
$dist = Join-Path $root 'dist'
$setup = Get-Item -LiteralPath (Join-Path $dist 'Frankesso-2.0.0-Windows-x64-Setup.exe')
$slices = @(Get-ChildItem -LiteralPath $dist -Filter 'Frankesso-2.0.0-Windows-x64-Setup-*.bin' -File |
    Sort-Object Name)
if ($slices.Count -lt 2) { throw 'The model installer did not produce its data slices.' }
$packageFiles = @($setup) + $slices
$checksums = foreach ($file in $packageFiles) {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    "$hash  $($file.Name)"
}
$checksums | Set-Content -Encoding ascii (Join-Path $dist 'SHA256SUMS.txt')
