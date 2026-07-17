param(
    [string]$Root = "",
    [string]$ScannerRoot = "",
    [switch]$AllowMissingExternalScanners
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    param([string]$RequestedRoot)

    if ($RequestedRoot) {
        return (Resolve-Path -LiteralPath $RequestedRoot).Path
    }

    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Find-Executable {
    param(
        [string]$Name,
        [string[]]$CandidatePaths
    )

    foreach ($candidate in $CandidatePaths) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    return $null
}

function Invoke-Step {
    param(
        [string]$Label,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "== $Label =="
    $global:LASTEXITCODE = 0
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

$repoRoot = Resolve-RepoRoot -RequestedRoot $Root

if (-not $ScannerRoot) {
    if ($env:CTL_SECURITY_SCANNERS) {
        $ScannerRoot = $env:CTL_SECURITY_SCANNERS
    } else {
        $workspaceScannerRoot = Join-Path $repoRoot "..\..\tools\security-scanners"
        if (Test-Path -LiteralPath $workspaceScannerRoot) {
            $ScannerRoot = (Resolve-Path -LiteralPath $workspaceScannerRoot).Path
        }
    }
}

$gitleaksCandidates = @()
$trufflehogCandidates = @()
if ($ScannerRoot) {
    $resolvedScannerRoot = (Resolve-Path -LiteralPath $ScannerRoot).Path
    $gitleaksCandidates += Join-Path $resolvedScannerRoot "gitleaks\gitleaks.exe"
    $trufflehogCandidates += Join-Path $resolvedScannerRoot "trufflehog\trufflehog.exe"
}

$gitleaks = Find-Executable -Name "gitleaks" -CandidatePaths $gitleaksCandidates
$trufflehog = Find-Executable -Name "trufflehog" -CandidatePaths $trufflehogCandidates

Write-Host "Scanning CTL-Core release root:"
Write-Host "  $repoRoot"

Invoke-Step "CTL local release safety scan" {
    python (Join-Path $repoRoot "scripts\check_release_safety.py") $repoRoot
}

if ($gitleaks) {
    Invoke-Step "gitleaks" {
        & $gitleaks dir $repoRoot --no-banner --redact --verbose
    }
} elseif ($AllowMissingExternalScanners) {
    Write-Warning "gitleaks not found; skipping because -AllowMissingExternalScanners was set."
} else {
    throw "gitleaks not found. Install it, set CTL_SECURITY_SCANNERS, pass -ScannerRoot, or rerun with -AllowMissingExternalScanners."
}

if ($trufflehog) {
    Invoke-Step "trufflehog" {
        $scanTargets = @(
            (Join-Path $repoRoot ".gitignore"),
            (Join-Path $repoRoot "CONTRIBUTING.md"),
            (Join-Path $repoRoot "LICENSE"),
            (Join-Path $repoRoot "README.md"),
            (Join-Path $repoRoot "SECURITY.md"),
            (Join-Path $repoRoot "THIRD_PARTY_NOTICES.md"),
            (Join-Path $repoRoot "requirements-demo.txt"),
            (Join-Path $repoRoot "ctl_core"),
            (Join-Path $repoRoot "docs"),
            (Join-Path $repoRoot "samples"),
            (Join-Path $repoRoot "scripts")
        ) | Where-Object { Test-Path -LiteralPath $_ }
        & $trufflehog filesystem @scanTargets --no-update --no-verification --no-color --json --fail --log-level=-1
    }
} elseif ($AllowMissingExternalScanners) {
    Write-Warning "trufflehog not found; skipping because -AllowMissingExternalScanners was set."
} else {
    throw "trufflehog not found. Install it, set CTL_SECURITY_SCANNERS, pass -ScannerRoot, or rerun with -AllowMissingExternalScanners."
}

Write-Host ""
Write-Host "Secret scan complete."
