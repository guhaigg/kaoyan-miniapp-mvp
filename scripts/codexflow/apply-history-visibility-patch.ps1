[CmdletBinding()]
param(
  [string]$InstallRoot = 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked',
  [string]$LaunchCmd = 'C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd',
  [string]$WorkRoot = [System.IO.Path]::Combine($env:TEMP, 'codexflow-history-visibility'),
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Trim-TrailingDirectorySeparators {
  param([Parameter(Mandatory = $true)][string]$PathValue)
  return $PathValue.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
}

function Resolve-NormalizedPath {
  param(
    [Parameter(Mandatory = $true)][string]$PathValue,
    [Parameter(Mandatory = $true)][string]$Label
  )

  if ([string]::IsNullOrWhiteSpace($PathValue)) {
    throw "$Label is empty."
  }

  $full = [System.IO.Path]::GetFullPath($PathValue)
  if ([string]::IsNullOrWhiteSpace($full)) {
    throw "Failed to normalize ${Label}: $PathValue"
  }

  return Trim-TrailingDirectorySeparators -PathValue $full
}

function Get-NormalizedRoot {
  param([Parameter(Mandatory = $true)][string]$PathValue)

  $root = [System.IO.Path]::GetPathRoot($PathValue)
  if ([string]::IsNullOrWhiteSpace($root)) {
    throw "Failed to resolve root path: $PathValue"
  }

  return Trim-TrailingDirectorySeparators -PathValue $root
}

function Test-IsPathUnder {
  param(
    [Parameter(Mandatory = $true)][string]$PathValue,
    [Parameter(Mandatory = $true)][string]$BasePath
  )

  $candidate = (Trim-TrailingDirectorySeparators -PathValue $PathValue) + [System.IO.Path]::DirectorySeparatorChar
  $base = (Trim-TrailingDirectorySeparators -PathValue $BasePath) + [System.IO.Path]::DirectorySeparatorChar
  return $candidate.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)
}

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

$normalizedInstallRoot = Resolve-NormalizedPath -PathValue $InstallRoot -Label 'InstallRoot'
$normalizedWorkRoot = Resolve-NormalizedPath -PathValue $WorkRoot -Label 'WorkRoot'
$normalizedExtractRoot = Resolve-NormalizedPath -PathValue (Join-Path $normalizedWorkRoot 'app') -Label 'ExtractRoot'
$workRootRoot = Get-NormalizedRoot -PathValue $normalizedWorkRoot

if ($normalizedWorkRoot -eq $workRootRoot) {
  throw "Unsafe WorkRoot: root path is not allowed ($normalizedWorkRoot)"
}
if ($normalizedExtractRoot -eq (Get-NormalizedRoot -PathValue $normalizedExtractRoot)) {
  throw "Unsafe extract root: root path is not allowed ($normalizedExtractRoot)"
}
if (-not (Test-IsPathUnder -PathValue $normalizedExtractRoot -BasePath $normalizedWorkRoot)) {
  throw "Unsafe extract root: $normalizedExtractRoot is not under WorkRoot $normalizedWorkRoot"
}
if ([System.IO.Path]::GetFileName($normalizedExtractRoot) -ne 'app') {
  throw "Unsafe extract root: expected leaf directory name 'app', got '$normalizedExtractRoot'"
}
if ((Test-IsPathUnder -PathValue $normalizedWorkRoot -BasePath $normalizedInstallRoot) -or (Test-IsPathUnder -PathValue $normalizedInstallRoot -BasePath $normalizedWorkRoot)) {
  throw "Unsafe path overlap: WorkRoot ($normalizedWorkRoot) must not overlap InstallRoot ($normalizedInstallRoot)"
}

$appAsarPath = Resolve-NormalizedPath -PathValue (Join-Path $normalizedInstallRoot 'resources\app.asar') -Label 'app.asar path'

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
if (-not (Test-Path -LiteralPath $normalizedInstallRoot -PathType Container)) {
  throw "InstallRoot not found: $normalizedInstallRoot"
}
if (-not (Test-Path -LiteralPath $appAsarPath -PathType Leaf)) {
  throw "Installed app.asar not found: $appAsarPath"
}

$runningProcesses = Get-Process -Name 'CodexFlow' -ErrorAction SilentlyContinue
if ($runningProcesses) {
  Write-Host 'CodexFlow process detected. Stopping before patch...'
  try {
    $runningProcesses | Stop-Process -Force -ErrorAction Stop
  }
  catch {
    throw "Failed to stop CodexFlow process: $($_.Exception.Message)"
  }

  Start-Sleep -Seconds 1
  $stillRunning = Get-Process -Name 'CodexFlow' -ErrorAction SilentlyContinue
  if ($stillRunning) {
    throw 'CodexFlow process is still running after stop attempt. Abort patching to avoid partial update.'
  }

  Write-Host 'CodexFlow process stopped.'
}

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
