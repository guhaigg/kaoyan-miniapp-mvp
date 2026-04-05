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

$normalizedInstallRoot = Resolve-NormalizedPath -PathValue $InstallRoot -Label 'InstallRoot'
$normalizedWorkRoot = Resolve-NormalizedPath -PathValue $WorkRoot -Label 'WorkRoot'
$normalizedExtractRoot = Resolve-NormalizedPath -PathValue (Join-Path $normalizedWorkRoot 'app') -Label 'ExtractRoot'
$appAsarPath = Resolve-NormalizedPath -PathValue (Join-Path $normalizedInstallRoot 'resources\app.asar') -Label 'app.asar path'

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

$asarArgs = @('exec', '--yes', '--package', '@electron/asar', '--', 'asar', 'extract', $appAsarPath, $normalizedExtractRoot)
$asarCmdText = 'npm ' + ($asarArgs -join ' ')

if ($DryRun) {
  Write-Host "DRYRUN extract => $asarCmdText"
  return
}

if (-not (Test-Path -LiteralPath $normalizedInstallRoot -PathType Container)) {
  throw "InstallRoot not found: $normalizedInstallRoot"
}
if (-not (Test-Path -LiteralPath $appAsarPath -PathType Leaf)) {
  throw "app.asar not found: $appAsarPath"
}
if ((Test-Path -LiteralPath $normalizedWorkRoot) -and -not (Test-Path -LiteralPath $normalizedWorkRoot -PathType Container)) {
  throw "WorkRoot exists but is not a directory: $normalizedWorkRoot"
}

if (Test-Path -LiteralPath $normalizedExtractRoot) {
  if (-not (Test-IsPathUnder -PathValue $normalizedExtractRoot -BasePath $normalizedWorkRoot)) {
    throw "Refusing to delete unmanaged path: $normalizedExtractRoot"
  }
  Remove-Item -LiteralPath $normalizedExtractRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $normalizedExtractRoot -Force | Out-Null

& npm @asarArgs
if ($LASTEXITCODE -ne 0) {
  throw "asar extract failed with exit code $LASTEXITCODE"
}

Write-Host "EXTRACT_ROOT=$normalizedExtractRoot"
