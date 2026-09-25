$err = $null
$target = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "_switch_to_official.ps1"   # ★ R1529：从本脚本位置推
$null = [System.Management.Automation.Language.Parser]::ParseFile($target, [ref]$null, [ref]$err)
if ($err -and $err.Count) { $err | ForEach-Object { "SYNTAX: " + $_.Message } } else { "syntax OK" }
