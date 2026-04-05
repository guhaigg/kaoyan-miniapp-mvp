[CmdletBinding()]
param(
  [string]$InstallRoot = 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked',
  [string]$WorkRoot = [System.IO.Path]::Combine($env:TEMP, 'codexflow-history-visibility'),
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$extractRoot = Join-Path $WorkRoot 'app'
$patchedAsarPath = Join-Path $WorkRoot 'app.patched.asar'
$appAsarPath = Join-Path $InstallRoot 'resources\app.asar'
$backupTimestamp = Get-Date -Format 'yyyyMMddHHmmss'
$backupPath = Join-Path $InstallRoot ("resources\app.asar.bak-$backupTimestamp")
$asarArgs = @('exec', '--yes', '--package', '@electron/asar', '--', 'asar', 'pack', $extractRoot, $patchedAsarPath)
$asarCmdText = 'npm ' + ($asarArgs -join ' ')

if ($DryRun) {
  Write-Host "DRYRUN pack => $asarCmdText"
  Write-Host "DRYRUN pack => backup $appAsarPath -> $backupPath"
  Write-Host "DRYRUN pack => replace $appAsarPath with $patchedAsarPath"
  return
}

if (-not (Test-Path -LiteralPath $InstallRoot -PathType Container)) {
  throw "InstallRoot not found: $InstallRoot"
}
if (-not (Test-Path -LiteralPath $extractRoot -PathType Container)) {
  throw "Extracted app directory not found: $extractRoot"
}
if (-not (Test-Path -LiteralPath $appAsarPath -PathType Leaf)) {
  throw "Installed app.asar not found: $appAsarPath"
}

& npm @asarArgs
if ($LASTEXITCODE -ne 0) {
  throw "asar pack failed with exit code $LASTEXITCODE"
}

Copy-Item -LiteralPath $appAsarPath -Destination $backupPath -Force
Copy-Item -LiteralPath $patchedAsarPath -Destination $appAsarPath -Force

Write-Host "BACKUP_CREATED=$backupPath"
Write-Host "PATCHED_ASAR=$patchedAsarPath"
