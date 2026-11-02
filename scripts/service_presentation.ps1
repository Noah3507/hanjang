[CmdletBinding()]
param([string]$ConfigFile,[ValidateRange(1024,65535)][int]$Port=8014,[switch]$CheckOnly)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
if(-not $ConfigFile){$ConfigFile=Join-Path $project 'artifacts/local-dev.json'}
if(-not(Test-Path -LiteralPath $ConfigFile -PathType Leaf)){throw 'Local config missing; follow README. Existing .env is not copied.'}
$config=Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8|ConvertFrom-Json
if(-not $config.resource_root -or -not [IO.Path]::IsPathRooted($config.resource_root)){throw 'Set absolute resource_root in ignored local config.'}
$resource=[IO.Path]::GetFullPath($config.resource_root)
$python=if($config.service_python){[string]$config.service_python}else{Join-Path $resource '.venv/Scripts/python.exe'}
$names=@('HANJANG_FRONTEND_DIST','HANJANG_PHOTO_MODEL_PATH','HANJANG_ANALYSIS_MODEL_PATH','HANJANG_ANALYSIS_PYTHON','HANJANG_RANKING_PYTHON','RANKING_MODEL_PATH','HANJANG_RANKING_MODE','HANJANG_RELEASE_REQUIRE_MODELS','HANJANG_UPLOAD_ROOT','HANJANG_RANKING_TEMP_ROOT','HANJANG_COPY_BUDGET_PATH','HANJANG_COPY_PROVIDER','HANJANG_COPY_ALLOW_PAID','HANJANG_COPY_MODEL','HANJANG_COPY_MAX_REQUESTS','HANJANG_COPY_BUDGET_USD','HANJANG_COPY_MAX_RETRIES','HANJANG_CORS_ORIGINS','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE')
$previous=@{};foreach($name in $names){$previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
Push-Location $project
try{
 $env:HANJANG_FRONTEND_DIST=Join-Path $project 'frontend/dist'
 $env:HANJANG_PHOTO_MODEL_PATH=if($config.photo_model){[string]$config.photo_model}else{Join-Path $resource 'artifacts/models/rembg/u2netp.onnx'}
 $env:HANJANG_ANALYSIS_PYTHON=if($config.analysis_python){[string]$config.analysis_python}else{Join-Path $resource '.venv-analysis/Scripts/python.exe'}
 $env:HANJANG_ANALYSIS_MODEL_PATH=if($config.clip_model){[string]$config.clip_model}else{Join-Path $resource 'artifacts/models/analysis/ViT-B-32.pt'}
 # Reuse the checked ASCII junction mechanism; it does not run a server/download.
 if($env:HANJANG_ANALYSIS_MODEL_PATH -match '[^\x00-\x7F]'){
  & (Join-Path $PSScriptRoot 'service_local.ps1') -ConfigFile $ConfigFile -CheckOnly
  if($config.clip_junction){$link=[string]$config.clip_junction}else{
   $sha=[Security.Cryptography.SHA256]::Create()
   try{$tag=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes((Split-Path $env:HANJANG_ANALYSIS_MODEL_PATH -Parent).ToLowerInvariant())))).Replace('-','').Substring(0,16)}finally{$sha.Dispose()}
   $link=Join-Path $env:LOCALAPPDATA "HanJang/model-links/$tag"
  }
  $env:HANJANG_ANALYSIS_MODEL_PATH=Join-Path $link (Split-Path $env:HANJANG_ANALYSIS_MODEL_PATH -Leaf)
 }
 $env:HANJANG_RANKING_PYTHON=if($config.ranking_python){[string]$config.ranking_python}else{Join-Path $resource '.venv-rank/Scripts/python.exe'}
 $env:RANKING_MODEL_PATH=if($config.ranking_model_path){[string]$config.ranking_model_path}else{Join-Path $resource 'artifacts/models/ranking/bt-logistic-v1/model.safetensors'}
 $env:HANJANG_RANKING_MODE=if($config.ranking_mode){[string]$config.ranking_mode}else{'model'}
 $env:HANJANG_RELEASE_REQUIRE_MODELS=if($config.require_models -eq $false){'false'}else{'true'}
 $runtime=if($config.runtime_root){[string]$config.runtime_root}else{Join-Path $project 'artifacts/presentation'}
 $env:HANJANG_UPLOAD_ROOT=Join-Path $runtime 'uploads';$env:HANJANG_RANKING_TEMP_ROOT=Join-Path $runtime 'ranking-snapshots'
 # Preserve the cumulative ledger across launches, ports and rollback; never reset it.
 $env:HANJANG_COPY_BUDGET_PATH=if($config.copy_budget_path){[string]$config.copy_budget_path}else{Join-Path $resource 'artifacts/copy-usage/ledger.json'}
 $env:HANJANG_COPY_PROVIDER=if($config.copy_provider){[string]$config.copy_provider}else{'mock'}
 $env:HANJANG_COPY_ALLOW_PAID=if($config.copy_allow_paid -eq $true){'true'}else{'false'}
 $env:HANJANG_COPY_MODEL='gpt-5.4-mini-2026-03-17'
 $env:HANJANG_COPY_MAX_REQUESTS=if($null -ne $config.copy_max_requests){[string]$config.copy_max_requests}else{'6'}
 $env:HANJANG_COPY_BUDGET_USD='0.10'
 $env:HANJANG_COPY_MAX_RETRIES='0'
 $env:HANJANG_CORS_ORIGINS='[]';$env:HF_HUB_OFFLINE='1';$env:TRANSFORMERS_OFFLINE='1'
 $arguments=@((Join-Path $PSScriptRoot 'service_serve.py'),'--port',[string]$Port)
 if($CheckOnly){$arguments+='--check-only'}
 & $python @arguments
 if($LASTEXITCODE -ne 0){throw 'Presentation process failed; inspect safe readiness checks. No tunnel was started.'}
}finally{Pop-Location;foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$previous[$name],'Process')}}
