<#! Windows local-only launcher. Never downloads or rewrites existing configuration. #>
[CmdletBinding()]
param(
    [string]$ConfigFile,
    [ValidateRange(1024,65535)][int]$Port = 8003,
    [ValidateRange(1024,65535)][int]$FrontendPort = 5176,
    [switch]$CheckOnly,
    [switch]$VerifyModels
)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
if (-not $ConfigFile) { $ConfigFile = Join-Path $project 'artifacts/local-dev.json' }
if (-not (Test-Path -LiteralPath $ConfigFile -PathType Leaf)) {
    throw 'Local config missing. Copy scripts/service_local.example.json to artifacts/local-dev.json and set resource_root. Do not copy .env or download models.'
}
$config = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-LocalFile([string]$field, [string]$fallback) {
    $value = $config.$field
    if (-not $value) { $value = Join-Path $resourceRoot $fallback }
    if (-not [IO.Path]::IsPathRooted($value) -or -not (Test-Path -LiteralPath $value -PathType Leaf)) {
        throw "Missing absolute path for $field. Repair local config; no automatic download/install is performed."
    }
    return [IO.Path]::GetFullPath($value)
}
if (-not $config.resource_root -or -not [IO.Path]::IsPathRooted($config.resource_root) -or
    -not (Test-Path -LiteralPath $config.resource_root -PathType Container)) {
    throw 'resource_root must name an existing absolute project/resource directory.'
}
$resourceRoot = [IO.Path]::GetFullPath($config.resource_root)
$python = Resolve-LocalFile 'service_python' '.venv/Scripts/python.exe'
$analysisPython = Resolve-LocalFile 'analysis_python' '.venv-analysis/Scripts/python.exe'
$photoModel = Resolve-LocalFile 'photo_model' 'artifacts/models/rembg/u2netp.onnx'
$clipModel = Resolve-LocalFile 'clip_model' 'artifacts/models/analysis/ViT-B-32.pt'
if ((Get-FileHash -LiteralPath $photoModel -Algorithm SHA256).Hash -ne '309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8' -or
    (Get-FileHash -LiteralPath $clipModel -Algorithm SHA256).Hash -ne '40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af') {
    throw 'Model checksum mismatch. Existing files were not changed; provision the documented exact models separately.'
}
if ($clipModel -match '[^\x00-\x7F]') {
    $target = Split-Path $clipModel -Parent
    $junction = $config.clip_junction
    if (-not $junction) {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $tag = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($target.ToLowerInvariant())))).Replace('-','').Substring(0,16) }
        finally { $sha.Dispose() }
        $junction = Join-Path $env:LOCALAPPDATA "HanJang/model-links/$tag"
    }
    if (-not [IO.Path]::IsPathRooted($junction) -or $junction -match '[^\x00-\x7F]') {
        throw 'clip_junction must be an absolute ASCII path. Set it explicitly in local config.'
    }
    $existing = Get-Item -LiteralPath $junction -Force -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.LinkType -ne 'Junction' -or @($existing.Target).Count -ne 1 -or
            [IO.Path]::GetFullPath([string]$existing.Target[0]).TrimEnd('\') -ine [IO.Path]::GetFullPath($target).TrimEnd('\')) {
            throw 'Existing clip_junction has a different target/type. It was not deleted or overwritten; choose another local path.'
        }
    } else {
        # Only a new empty parent and a directory link are created, never model copies.
        New-Item -ItemType Directory -Path (Split-Path $junction -Parent) -Force | Out-Null
        New-Item -ItemType Junction -Path $junction -Value $target | Out-Null
    }
    $clipModel = Join-Path $junction (Split-Path $clipModel -Leaf)
    if (-not (Test-Path -LiteralPath $clipModel -PathType Leaf)) { throw 'CLIP junction target is unavailable; repair local config.' }
}
$names = @('HANJANG_PHOTO_MODEL_PATH','HANJANG_ANALYSIS_MODEL_PATH','HANJANG_ANALYSIS_PYTHON','HANJANG_UPLOAD_ROOT',
    'HANJANG_COPY_PROVIDER','HANJANG_COPY_ALLOW_PAID','OPENAI_API_KEY','HANJANG_CORS_ORIGINS','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','PYTHONUTF8','PYTHONPATH')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
Push-Location $project
try {
    $env:HANJANG_PHOTO_MODEL_PATH = $photoModel
    $env:HANJANG_ANALYSIS_MODEL_PATH = $clipModel
    $env:HANJANG_ANALYSIS_PYTHON = $analysisPython
    $env:HANJANG_UPLOAD_ROOT = Join-Path $project 'artifacts/local-dev/uploads'
    $env:HANJANG_COPY_PROVIDER = 'mock'
    $env:HANJANG_COPY_ALLOW_PAID = 'false'
    $env:OPENAI_API_KEY = ''
    $env:HANJANG_CORS_ORIGINS = "[`"http://127.0.0.1:$FrontendPort`",`"http://localhost:$FrontendPort`"]"
    $env:HF_HUB_OFFLINE = '1'; $env:TRANSFORMERS_OFFLINE = '1'; $env:PYTHONUTF8 = '1'
    $env:PYTHONPATH = Join-Path $project 'backend'
    & $python -c "import sys,rembg,onnxruntime,fontTools; print('Service environment OK:',sys.prefix)"
    if ($LASTEXITCODE -ne 0) { throw 'Service environment failed; use the documented service Python. No packages were installed.' }
    & $analysisPython -c "import sys,torch,open_clip; print('Analysis environment OK:',sys.prefix)"
    if ($LASTEXITCODE -ne 0) { throw 'Analysis environment failed; use the documented separate analysis Python.' }
    if ($VerifyModels) {
        & $python (Join-Path $PSScriptRoot 'service_model_check.py')
        if ($LASTEXITCODE -ne 0) { throw 'Offline model loading check failed. Inspect the safe error; do not download substitute models.' }
    }
    Write-Host "Project: $project"
    Write-Host "rembg: $photoModel"
    Write-Host "CLIP: $clipModel"
    if (-not $CheckOnly) {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$Port)
        try { $listener.Start() } catch { throw "Port $Port is occupied. Existing process was not stopped; choose another port." }
        finally { $listener.Stop() }
        Write-Host "Mock-only backend: http://127.0.0.1:$Port/docs (Ctrl+C to stop)"
        & $python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
        if ($LASTEXITCODE -ne 0) { throw 'Backend exited unsuccessfully. Inspect server output.' }
    }
} finally {
    Pop-Location
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
}
