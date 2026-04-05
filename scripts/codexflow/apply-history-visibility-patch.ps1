[CmdletBinding()]
param(
  [string]$InstallRoot = 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked',
  [string]$LaunchCmd = 'C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd',
  [string]$WorkRoot = [System.IO.Path]::Combine($env:TEMP, 'codexflow-history-visibility'),
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$extractScript = Join-Path $PSScriptRoot 'extract-installed-codexflow.ps1'
$packScript = Join-Path $PSScriptRoot 'pack-installed-codexflow.ps1'
$extractRoot = Join-Path $WorkRoot 'app'
$helperSource = Join-Path $repoRoot 'scripts\codexflow\lib\historyVisibility.cjs'
$patchScript = Join-Path $repoRoot 'scripts\codexflow\lib\patchInstalledFiles.cjs'

$extractArgs = @('-ExecutionPolicy', 'Bypass', '-File', $extractScript, '-InstallRoot', $InstallRoot, '-LaunchCmd', $LaunchCmd, '-WorkRoot', $WorkRoot)
$packArgs = @('-ExecutionPolicy', 'Bypass', '-File', $packScript, '-InstallRoot', $InstallRoot, '-WorkRoot', $WorkRoot)
$patchArgs = @($patchScript, '--extract-root', $extractRoot, '--helper-source', $helperSource)

$extractCmdText = 'powershell ' + ($extractArgs -join ' ')
$patchCmdText = 'node ' + ($patchArgs -join ' ')
$packCmdText = 'powershell ' + ($packArgs -join ' ')

if ($DryRun) {
  Write-Host "DRYRUN extract => npm exec --yes --package @electron/asar -- asar extract <app.asar> <workroot\\app>"
  Write-Host "DRYRUN extract-call => $extractCmdText -DryRun"
  Write-Host "DRYRUN patch => $patchCmdText"
  Write-Host "DRYRUN pack => npm exec --yes --package @electron/asar -- asar pack <workroot\\app> <workroot\\app.patched.asar>"
  Write-Host "DRYRUN pack-call => $packCmdText -DryRun"
  if ($LaunchCmd) {
    Write-Host "DRYRUN launch => $LaunchCmd"
  }
  return
}

if (-not (Test-Path -LiteralPath $extractScript -PathType Leaf)) {
  throw "Extract script not found: $extractScript"
}
if (-not (Test-Path -LiteralPath $packScript -PathType Leaf)) {
  throw "Pack script not found: $packScript"
}
if (-not (Test-Path -LiteralPath $patchScript -PathType Leaf)) {
  throw "Patch script not found: $patchScript"
}
if (-not (Test-Path -LiteralPath $helperSource -PathType Leaf)) {
  throw "Helper source not found: $helperSource"
}

Get-Process -Name 'CodexFlow' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

& powershell @extractArgs
if ($LASTEXITCODE -ne 0) {
  throw "Extract step failed with exit code $LASTEXITCODE"
}

& node @patchArgs
if ($LASTEXITCODE -ne 0) {
  throw "Patch step failed with exit code $LASTEXITCODE"
}

& powershell @packArgs
if ($LASTEXITCODE -ne 0) {
  throw "Pack step failed with exit code $LASTEXITCODE"
}

if ($LaunchCmd -and (Test-Path -LiteralPath $LaunchCmd -PathType Leaf)) {
  Start-Process -FilePath $LaunchCmd | Out-Null
  Write-Host "LAUNCH_STARTED=$LaunchCmd"
}
