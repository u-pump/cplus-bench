$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scriptPath = Join-Path $PSScriptRoot 'run-agent-local.ps1'
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -ne 0) { throw "PowerShell syntax errors: $($errors | Out-String)" }
. (Join-Path $PSScriptRoot 'agent_evidence.ps1')
$init = '{"type":"system","subtype":"init","model":"claude-test"}'
$okTool = '{"type":"user","message":{"content":[{"type":"tool_result","is_error":false}]}}'
$badTool = '{"type":"user","message":{"content":[{"type":"tool_result","is_error":true}]}}'
$success = '{"type":"result","subtype":"success","is_error":false}'
$failure = '{"type":"result","subtype":"error","is_error":true}'
if ((Get-ClaudeEvidence -Log "$init`n$okTool`n$success") -ne 'claude-test') { throw 'Completed Claude run was not recognized' }
foreach ($log in @("$init`n$success", "$init`n$badTool`n$success", "$init`n$okTool`n$failure")) {
    try { Get-ClaudeEvidence -Log $log | Out-Null; throw 'Incomplete Claude run was accepted' }
    catch { if ($_.Exception.Message -notmatch 'attempt not recorded') { throw } }
}

$caseId = 'cpp-peglib-121'
$codexPatch = Join-Path $root "cases/$caseId/agents/codex-cli/agent-fix.patch"
$codexHash = (Get-FileHash -LiteralPath $codexPatch -Algorithm SHA256).Hash
try { & $scriptPath -Agent codex-cli $caseId; throw 'Recorded Codex patch was accepted for overwrite' }
catch { if ($_.Exception.Message -notmatch 'First patch already recorded') { throw } }
if ((Get-FileHash -LiteralPath $codexPatch -Algorithm SHA256).Hash -ne $codexHash) { throw 'Recorded patch changed' }

$claudePatch = Join-Path $root "cases/$caseId/agents/claude-code/agent-fix.patch"
$claudeMeta = Join-Path $root "cases/$caseId/agents/claude-code/agent.yaml"
$beforePatch = [IO.File]::ReadAllBytes($claudePatch)
$beforeMeta = [IO.File]::ReadAllBytes($claudeMeta)
function claude {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq '--version') { return '2.1.309 (Claude Code)' }
    if ($args[0] -eq 'auth') { return '{"loggedIn":true,"authMethod":"oauth"}' }
    if ($args[0] -eq '--help') { return '--print --restricted --tools --disallowedTools --strict-mcp-config --output-format --no-session-persistence --permission-prompts' }
    throw 'Agent execution is forbidden in this test'
}
function gh { $global:LASTEXITCODE = 0; return '' }
try { & $scriptPath -Agent claude-code $caseId; throw 'Missing GitHub token was accepted' }
catch { if ($_.Exception.Message -notmatch 'GitHub token unavailable') { throw } }
if (-not [Linq.Enumerable]::SequenceEqual([byte[]][IO.File]::ReadAllBytes($claudePatch), [byte[]]$beforePatch)) { throw 'Pending patch changed' }
if (-not [Linq.Enumerable]::SequenceEqual([byte[]][IO.File]::ReadAllBytes($claudeMeta), [byte[]]$beforeMeta)) { throw 'Pending metadata changed' }
Write-Host 'run-agent-local.ps1 preflight tests passed; no agent launched'
