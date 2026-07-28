[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$MessageParts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Assert-NativeSuccess {
    param([string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found in PATH."
}

if ($MessageParts.Count -gt 0) {
    $CommitMessage = ($MessageParts -join ' ').Trim()
}
else {
    $CommitMessage = "Auto update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

git add -A
Assert-NativeSuccess "git add"

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "No changes to commit." -ForegroundColor Yellow
    exit 0
}

git commit -m $CommitMessage
Assert-NativeSuccess "git commit"

git push
Assert-NativeSuccess "git push"

Write-Host "Committed and pushed: $CommitMessage" -ForegroundColor Green
