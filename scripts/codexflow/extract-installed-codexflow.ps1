[CmdletBinding()]
param(
  [string]$InstallRoot = 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked',
  [string]$LaunchCmd = 'C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd',
  [string]$WorkRoot = [System.IO.Path]::Combine($env:TEMP, 'codexflow-history-visibility'),
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$appAsarPath = Join-Path $InstallRoot 'resources\app.asar'
$extractRoot = Join-Path $WorkRoot 'app'
$asarArgs = @('exec', '--yes', '--package', '@electron/asar', '--', 'asar', 'extract', $appAsarPath, $extractRoot)
$asarCmdText = 'npm ' + ($asarArgs -join ' ')

if ($DryRun) {
  Write-Host "DRYRUN extract => $asarCmdText"
  return
}

if (-not (Test-Path -LiteralPath $InstallRoot -PathType Container)) {
  throw "InstallRoot not found: $InstallRoot"
}
if (-not (Test-Path -LiteralPath $appAsarPath -PathType Leaf)) {
  throw "app.asar not found: $appAsarPath"
}

if (Test-Path -LiteralPath $extractRoot) {
  Remove-Item -LiteralPath $extractRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null

& npm @asarArgs
if ($LASTEXITCODE -ne 0) {
  throw "asar extract failed with exit code $LASTEXITCODE"
}

Write-Host "EXTRACT_ROOT=$extractRoot"
