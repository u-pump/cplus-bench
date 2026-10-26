param(
    [Parameter(Mandatory, Position = 0)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]*$')][string]$CaseId,
    [ValidateSet('codex-cli', 'claude-code')][string]$Agent = 'codex-cli'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'agent_evidence.ps1')
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$caseDir = Join-Path $root "cases/$CaseId"
$agentDir = Join-Path $caseDir "agents/$Agent"
$patchPath = Join-Path $agentDir 'agent-fix.patch'
$metaPath = Join-Path $agentDir 'agent.yaml'
$checkoutRoot = Join-Path (Split-Path -Parent $root) ".tmp/bench-agent/$Agent"
$checkout = Join-Path $checkoutRoot $CaseId
$logDir = Join-Path $root '.tmp/agent-runs/logs'
$runId = "$CaseId-$Agent-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$logPath = Join-Path $logDir "$runId.log"
$candidate = Join-Path $logDir "$runId.patch"
$repo = "u-pump/bench-in-$CaseId"
if (-not (Test-Path -LiteralPath $caseDir -PathType Container)) { throw "Unknown case: $CaseId" }
if (-not (Test-Path -LiteralPath $patchPath -PathType Leaf)) { throw "Missing agent-fix.patch: $Agent" }
if ((Get-Item -LiteralPath $patchPath).Length -ne 0) { throw "First patch already recorded: $Agent/$CaseId" }
if (Test-Path -LiteralPath $checkout) { throw "Checkout already exists: $checkout" }
$command = if ($Agent -eq 'claude-code') { 'claude' } else { 'codex' }
if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
    if ($Agent -eq 'claude-code') { throw 'Claude Code не найден. Установите его по https://code.claude.com/docs/en/setup, затем выполните claude и войдите в аккаунт.' }
    throw 'Codex CLI не найден'
}
$version = (& $command --version).Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) { throw "$command --version failed" }
if ($Agent -eq 'claude-code') {
    try {
        $auth = & claude auth status | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or -not $auth.loggedIn) { throw 'not logged in' }
    } catch { throw 'Claude Code не авторизован. Выполните claude и войдите в аккаунт.' }
    $bare = $auth.authMethod -eq 'api_key' -and -not [string]::IsNullOrWhiteSpace($env:ANTHROPIC_API_KEY)
    $helpText = (& claude --help) -join "`n"
    foreach ($flag in @('--print', '--restricted', '--tools', '--disallowedTools', '--strict-mcp-config', '--output-format', '--no-session-persistence', '--permission-prompts')) {
        if (-not $helpText.Contains($flag)) { throw "Claude Code не поддерживает $flag; обновите CLI" }
    }
}
$oldGhToken = $env:GH_TOKEN
$oldGithubToken = $env:GITHUB_TOKEN
try {
    $env:GH_TOKEN = (gh auth token --user u-pump).Trim()
    if (-not $env:GH_TOKEN) { throw 'u-pump GitHub token unavailable' }
    if ((gh repo view $repo --json isPrivate --jq '.isPrivate') -ne 'true') { throw "Input repository is not private: $repo" }
    New-Item -ItemType Directory -Force -Path $checkoutRoot, $logDir | Out-Null
    gh repo clone $repo $checkout -- --depth 1 --single-branch
    if ($LASTEXITCODE -ne 0) { throw "Clone failed: $repo" }
    $checkoutTop = (git -C $checkout rev-parse --show-toplevel).Trim()
    if ([IO.Path]::GetFullPath($checkoutTop).TrimEnd('\') -ne [IO.Path]::GetFullPath($checkout).TrimEnd('\')) {
        throw 'Unexpected checkout root'
    }
    if ((git -C $checkout rev-list --count HEAD) -ne '1' -or (git -C $checkout cat-file -p HEAD | Select-String '^parent ')) {
        throw 'Input repository does not have one root commit'
    }
    $taskPath = Join-Path $checkout 'TASK.md'
    if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) { throw 'TASK.md missing' }
    $task = (Get-Content -LiteralPath $taskPath -Raw -Encoding UTF8).Trim()
    if ($task -ne 'Fix the bug described in ISSUE.md. Keep the change minimal. Run the existing tests.') { throw 'TASK.md differs from the benchmark protocol' }
    $env:GH_TOKEN = $null
    $env:GITHUB_TOKEN = $null
    Write-Host "$Agent $version; log: $logPath"
    Push-Location -LiteralPath $checkout
    try {
        if ($Agent -eq 'claude-code') {
            $claudeArgs = @('-p', '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
                '--restricted', '--strict-mcp-config', '--disable-slash-commands',
                '--permission-mode', 'acceptEdits', '--permission-prompts', 'none',
                '--tools', 'Bash,PowerShell,Read,Edit,Write,Glob,Grep', '--disallowedTools', 'WebSearch,WebFetch')
            if ($bare) { $claudeArgs += '--bare' }
            & claude @claudeArgs $task 2>&1 | Tee-Object -FilePath $logPath
        } else {
            & codex exec --sandbox workspace-write $task 2>&1 | Tee-Object -FilePath $logPath
        }
        $agentExit = $LASTEXITCODE
    } finally { Pop-Location }
    $log = Get-Content -LiteralPath $logPath -Raw -Encoding UTF8
    if ($agentExit -ne 0) { throw "$Agent exited with code $agentExit; attempt not recorded. See $logPath" }
    if ($Agent -eq 'claude-code') {
        $model = Get-ClaudeEvidence -Log $log
        $environment = if ($bare) {
            'local Windows; --bare and --restricted; built-in web tools denied; settings, auto-memory and CLAUDE.md skipped; Bash/PowerShell network, host files and saved credentials not OS-isolated'
        } else {
            'local Windows; --restricted; built-in web tools denied; user/project settings ignored; CLAUDE.md may load; Bash/PowerShell network, host files and saved credentials not OS-isolated'
        }
        $invocation = 'claude -p --restricted --strict-mcp-config --tools Bash,PowerShell,Read,Edit,Write,Glob,Grep --disallowedTools WebSearch,WebFetch'
        if ($bare) { $invocation += ' --bare' }
        $name = 'Claude Code'
    } else {
        $modelMatch = [regex]::Match($log, '(?m)^model:\s*(\S+)')
        $model = if ($modelMatch.Success) { $modelMatch.Groups[1].Value } else { '' }
        if (-not $model -or -not [regex]::IsMatch($log, '(?m)^exec\r?$') -or
            -not [regex]::IsMatch($log, '(?m)^ (?:succeeded|exited \d+) in ')) {
            throw "Codex CLI executed no completed commands; attempt not recorded. See $logPath"
        }
        $environment = 'local Windows; Codex workspace-write sandbox; network restriction depends on CLI sandbox configuration'
        $invocation = 'codex exec --sandbox workspace-write'
        $name = 'Codex CLI'
    }
    git -C $checkout add -A -- . ':(exclude,glob)build*/**' ':(exclude,glob)**/build*/**'
    if ($LASTEXITCODE -ne 0) { throw 'Could not stage agent changes' }
    git -C $checkout diff --cached --binary --no-ext-diff --output=$candidate HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Could not save agent patch' }
    $hash = if ((Get-Item -LiteralPath $candidate).Length -eq 0) { $null } else {
        (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $metadata = [ordered]@{
        name = $name; version = $version; model = $model; invocation = $invocation
        date_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        environment = $environment; patch_sha256 = $hash
        attempt_note = 'First completed local attempt; build*/ output excluded from the patch.'
    }
    Copy-Item -LiteralPath $candidate -Destination $patchPath
    try { $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metaPath -Encoding utf8 }
    catch { [IO.File]::WriteAllBytes($patchPath, [byte[]]@()); throw }
    Write-Host "Patch: $patchPath; SHA-256: $hash"
} finally {
    $env:GH_TOKEN = $oldGhToken
    $env:GITHUB_TOKEN = $oldGithubToken
    $rootFull = [IO.Path]::GetFullPath($checkoutRoot).TrimEnd('\')
    $checkoutFull = [IO.Path]::GetFullPath($checkout)
    if (-not $checkoutFull.StartsWith("$rootFull\", [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe checkout cleanup path' }
    if (Test-Path -LiteralPath $checkoutFull) { Remove-Item -LiteralPath $checkoutFull -Recurse -Force }
}
