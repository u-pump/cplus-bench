$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scriptPath = Join-Path $PSScriptRoot 'run-agent-local.ps1'
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -ne 0) { throw "PowerShell syntax errors: $($errors | Out-String)" }
. (Join-Path $PSScriptRoot 'agent_evidence.ps1')

$init = '{"type":"system","subtype":"init","model":"claude-test"}'
$bash = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"bash-1","input":{"command":"cmake --build build"}}]}}'
$edit = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"edit-1"}]}}'
$okBash = '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"bash-1","is_error":false,"content":"Exit code: 0\nBuild passed"}]}}'
$badBash = '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"bash-1","is_error":false,"content":"Exit code: 1\nBuild failed"}]}}'
$okEdit = '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"edit-1","is_error":false,"content":"edited"}]}}'
$success = '{"type":"result","subtype":"success","is_error":false}'
$failure = '{"type":"result","subtype":"error","is_error":true}'
if ((Get-ClaudeEvidence -Log "$init`n$bash`n$okBash`n$success") -ne 'claude-test') { throw 'Successful Bash run was not recognized' }
foreach ($log in @(
    "$init`n$success", "$init`n$edit`n$okEdit`n$success",
    "$init`n$bash`n$badBash`n$success", "$init`n$bash`n$okBash`n$failure"
)) {
    try { Get-ClaudeEvidence -Log $log | Out-Null; throw 'Incomplete Claude run was accepted' }
    catch { if ($_.Exception.Message -notmatch 'attempt not recorded') { throw } }
}

$settingsJson = New-ClaudeSettings
$settings = $settingsJson | ConvertFrom-Json
if (-not $settings.sandbox.enabled -or -not $settings.sandbox.failIfUnavailable -or
    -not $settings.sandbox.autoAllowBashIfSandboxed -or $settings.sandbox.allowUnsandboxedCommands -or
    -not $settings.sandbox.network.strictAllowlist -or
    @($settings.sandbox.network.allowedDomains).Count -ne 0 -or
    @($settings.sandbox.excludedCommands).Count -ne 0 -or
    $settings.sandbox.filesystem.disabled -or
    $settings.sandbox.filesystem.denyRead -notcontains '~/' -or
    $settings.sandbox.filesystem.denyRead -notcontains '/mnt' -or
    $settings.sandbox.filesystem.allowRead -notcontains '.' -or
    -not $settings.permissions.blockReadsOutsideWorkingDirectories) {
    throw 'Claude sandbox settings are not fail-closed'
}
foreach ($rule in @('Read(~/)', 'Read(~/**)', 'Read(//mnt)', 'Read(//mnt/**)',
    'Edit(~/)', 'Edit(~/**)', 'Edit(//mnt)', 'Edit(//mnt/**)')) {
    if ($settings.permissions.deny -notcontains $rule) { throw "Missing file-tool deny: $rule" }
}
Assert-ClaudeSettingsPolicy -SettingsJson $settingsJson
$badSettings = $settingsJson.Replace('"/mnt"', '"/missing"')
try { Assert-ClaudeSettingsPolicy -SettingsJson $badSettings; throw 'Weak sandbox accepted' }
catch { if ($_.Exception.Message -notmatch 'не запрещают') { throw } }
$claudeCheckoutRoot = Get-AgentCheckoutRoot -Agent 'claude-code' -BenchmarkRoot $root
if ($claudeCheckoutRoot -ne '/var/tmp/cplus-bench-agent/claude-code' -or
    $claudeCheckoutRoot.StartsWith('/mnt/') -or $claudeCheckoutRoot.StartsWith('~/')) {
    throw 'Claude checkout is not isolated from home and /mnt'
}

$networkLog = "$init`n" +
    '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"net-1","input":{"command":"curl https://example.com/private/path"}},{"type":"tool_use","name":"WebSearch","id":"net-2","input":{}}]}}' + "`n" +
    '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"net-1","is_error":true,"content":"host_not_allowed example.com"}]}}' + "`n" + $success
$attempts = Get-ClaudeNetworkAttempts -Log $networkLog
if ($attempts.count -ne 2 -or @($attempts.commands).Count -ne 2 -or
    $attempts.commands -notcontains 'curl' -or $attempts.commands -notcontains 'WebSearch') {
    throw 'Network attempts were not counted or sanitized'
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
    if ($args[0] -eq '--version') { return '2.1.310 (Claude Code)' }
    throw 'Agent execution is forbidden in this test'
}
if (-not $IsLinux) {
    try { & $scriptPath -Agent claude-code $caseId; throw 'Native Windows was accepted' }
    catch { if ($_.Exception.Message -notmatch 'WSL2 Ubuntu') { throw } }
} else {
    try { Assert-ClaudeSandboxHost; throw 'Non-WSL Linux was accepted' }
    catch { if ($_.Exception.Message -notmatch 'WSL2 Ubuntu') { throw } }
}
if (-not [Linq.Enumerable]::SequenceEqual([byte[]][IO.File]::ReadAllBytes($claudePatch), [byte[]]$beforePatch)) { throw 'Pending patch changed' }
if (-not [Linq.Enumerable]::SequenceEqual([byte[]][IO.File]::ReadAllBytes($claudeMeta), [byte[]]$beforeMeta)) { throw 'Pending metadata changed' }
Write-Host 'run-agent-local.ps1 sandbox/evidence tests passed; no agent launched'
