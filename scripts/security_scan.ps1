<#!
Security scan stub.
Runs (if available):
  - bandit (static analysis)
  - pip-audit (dependency vulnerabilities)
Outputs JSON summaries to artifacts/security/.
Gracefully degrades if tools not installed.
#>
param(
  [string]$OutputDir = "artifacts/security"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null }

Write-Host "[+] Security scan starting..."

function Invoke-ToolOrPlaceholder {
  param(
    [string]$Cmd,
    [string]$ToolArgs,
    [string]$OutFile,
    [string]$PlaceholderMessage
  )
  if (Get-Command $Cmd -ErrorAction SilentlyContinue) {
    Write-Host "[>] Running $Cmd $ToolArgs"
    & $Cmd $ToolArgs | Out-File -Encoding utf8 $OutFile
  } else {
    "{`"warning`":`"$PlaceholderMessage`"}" | Out-File -Encoding utf8 $OutFile
    Write-Host "[!] $Cmd not installed; wrote placeholder $OutFile"
  }
}

$banditOut = Join-Path $OutputDir "bandit_report.json"
Invoke-ToolOrPlaceholder -Cmd "bandit" -ToolArgs "-q -r src -f json" -OutFile $banditOut -PlaceholderMessage "bandit not installed"

$pipAuditOut = Join-Path $OutputDir "pip_audit_report.json"
Invoke-ToolOrPlaceholder -Cmd "pip-audit" -ToolArgs "-r requirements.txt -f json" -OutFile $pipAuditOut -PlaceholderMessage "pip-audit not installed"

$summary = [pscustomobject]@{
  timestamp = (Get-Date).ToUniversalTime().ToString("o")
  bandit_report = Get-Content $banditOut -Raw
  pip_audit_report = Get-Content $pipAuditOut -Raw
}
$summaryPath = Join-Path $OutputDir "security_summary.json"
$summary | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 $summaryPath
Write-Host "[+] Summary -> $summaryPath"
Write-Host "[+] Security scan complete."
