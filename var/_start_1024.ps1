param(
  [switch]$WaitUntilStart,
  [string]$Strategy = "speedc151",
  [string]$TokenFile = "var\.token_1024_20260917",
  [string]$Server = "https://10.240.169.190:18080",
  [datetime]$StartAt = [datetime]'2026-09-17T19:45:00'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if ($WaitUntilStart) {
  $target = $StartAt
  $wait = ($target - [datetime]::Now).TotalSeconds
  if ($wait -gt 0) { Start-Sleep -Seconds ([int]$wait) }
}
& python -X utf8 var/_official_keepalive.py --strategy $Strategy --token-file $TokenFile --server $Server
