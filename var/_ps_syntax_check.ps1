$err = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile("D:\hangzhouMaj\var\_switch_to_official.ps1", [ref]$null, [ref]$err)
if ($err -and $err.Count) { $err | ForEach-Object { "SYNTAX: " + $_.Message } } else { "syntax OK" }
