# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
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
$checkoutRoot = Get-AgentCheckoutRoot -Agent $Agent -BenchmarkRoot $root
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
    Assert-ClaudeSandboxHost
    $claudeSource = (Get-Command claude).Source
    if ($claudeSource -match '^/mnt/|\.exe$|\.cmd$') {
        throw 'Нужна Linux-версия Claude Code внутри WSL2, а не Windows-программа. См. docs/run-agent.md.'
    }
    if ($root -match '^/mnt/[a-z]/') {
        throw 'Для песочницы WSL2 храните unfix-bench в файловой системе Ubuntu (например ~/unfix-bench), не в /mnt/c или /mnt/d.'
    }
    try {
        $authOutput = & claude auth status
        $auth = $authOutput | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or $auth.loggedIn -ne $true -or
            -not ($auth.PSObject.Properties.Name -contains 'authMethod') -or
            [string]::IsNullOrWhiteSpace([string]$auth.authMethod)) { throw 'invalid auth status' }
    } catch { throw 'Claude Code не авторизован. Выполните claude auth login в WSL2.' }
    $helpText = (& claude --help) -join "`n"
    foreach ($flag in @('--print', '--restricted', '--safe-mode', '--tools', '--disallowedTools',
        '--strict-mcp-config', '--output-format', '--no-session-persistence',
        '--permission-prompts', '--settings', '--permission-mode')) {
        if (-not $helpText.Contains($flag)) { throw "Claude Code не поддерживает $flag; обновите CLI" }
    }
    $claudeSettings = New-ClaudeSettings
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
    if ($Agent -eq 'claude-code') {
        Assert-ClaudeSettingsIsolation -SettingsJson $claudeSettings -Checkout $checkout
    }
    $env:GH_TOKEN = $null
    $env:GITHUB_TOKEN = $null
    Write-Host "$Agent $version; log: $logPath"
    Push-Location -LiteralPath $checkout
    try {
        if ($Agent -eq 'claude-code') {
            $claudeArgs = @('-p', '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
                '--restricted', '--safe-mode', '--strict-mcp-config', '--disable-slash-commands',
                '--permission-mode', 'acceptEdits', '--permission-prompts', 'none',
                '--settings', $claudeSettings,
                '--tools', 'Bash,Read,Edit,Write,Glob,Grep', '--disallowedTools', 'WebSearch,WebFetch')
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
        $networkAttempts = Get-ClaudeNetworkAttempts -Log $log
        $osName = (Get-Content -LiteralPath '/etc/os-release' | Where-Object { $_ -like 'PRETTY_NAME=*' } | Select-Object -First 1) -replace '^PRETTY_NAME="?(.*?)"?$', '$1'
        $environment = "WSL2 $osName; Claude Code sandbox enabled/failIfUnavailable; auto-allow Bash inside sandbox; strict empty network allowlist; unsandboxed commands disabled; seccomp filter required; --restricted --safe-mode; Bash denyRead ~/ and /mnt, allowRead checkout; file tools deny home and /mnt, blockReadsOutsideWorkingDirectories; system paths and other /var/tmp paths may remain readable"
        $invocation = 'claude -p --restricted --safe-mode --strict-mcp-config --permission-mode acceptEdits --permission-prompts none --settings <strict sandbox JSON> --tools Bash,Read,Edit,Write,Glob,Grep --disallowedTools WebSearch,WebFetch'
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
    if ($Agent -eq 'claude-code') { $metadata.network_attempts = $networkAttempts }
    Copy-Item -LiteralPath $candidate -Destination $patchPath
    try { $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metaPath -Encoding utf8 }
    catch { [IO.File]::WriteAllBytes($patchPath, [byte[]]@()); throw }
    Write-Host "Patch: $patchPath; SHA-256: $hash"
} finally {
    $env:GH_TOKEN = $oldGhToken
    $env:GITHUB_TOKEN = $oldGithubToken
    $separator = [IO.Path]::DirectorySeparatorChar
    $rootFull = [IO.Path]::GetFullPath($checkoutRoot).TrimEnd($separator)
    $checkoutFull = [IO.Path]::GetFullPath($checkout)
    if (-not $checkoutFull.StartsWith("$rootFull$separator", [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe checkout cleanup path' }
    if (Test-Path -LiteralPath $checkoutFull) { Remove-Item -LiteralPath $checkoutFull -Recurse -Force }
}
