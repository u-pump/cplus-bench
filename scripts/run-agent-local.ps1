param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]*$')]
    [string]$CaseId,
    [string]$Model = 'gpt-6-sol'
)

$ErrorActionPreference = 'Stop'
$benchRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$caseDir = Join-Path $benchRoot "cases/$CaseId"
$patchPath = Join-Path $caseDir 'agent-fix.patch'
$agentRoot = 'D:\bench-agent'
$checkout = Join-Path $agentRoot $CaseId
$logDir = Join-Path $benchRoot '.tmp/agent-runs'
$logPath = Join-Path $logDir "$CaseId-$(Get-Date -Format 'yyyyMMdd-HHmmss').jsonl"
$repo = "u-pump/bench-in-$CaseId"

if (-not (Test-Path -LiteralPath $caseDir -PathType Container)) { throw "Unknown case: $CaseId" }
if (-not (Test-Path -LiteralPath $patchPath -PathType Leaf)) { throw 'Missing agent-fix.patch' }
if ((Get-Item -LiteralPath $patchPath).Length -ne 0) { throw 'First patch already recorded' }
if (Test-Path -LiteralPath $checkout) { throw "Checkout already exists: $checkout" }
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw 'Codex CLI not found' }

$oldGhToken = $env:GH_TOKEN
$oldGithubToken = $env:GITHUB_TOKEN
try {
    $env:GH_TOKEN = (gh auth token --user u-pump).Trim()
    if (-not $env:GH_TOKEN) { throw 'u-pump GitHub token unavailable' }
    if ((gh repo view $repo --json isPrivate --jq '.isPrivate') -ne 'true') {
        throw "Input repository is not private: $repo"
    }
    New-Item -ItemType Directory -Force -Path $agentRoot, $logDir | Out-Null
    gh repo clone $repo $checkout -- --depth 1 --single-branch
    if ($LASTEXITCODE -ne 0) { throw "Clone failed: $repo" }

    if ((git -C $checkout rev-list --count HEAD) -ne '1' -or
        (git -C $checkout cat-file -p HEAD | Select-String '^parent ')) {
        throw 'Input repository does not have one root commit'
    }
    $taskPath = Join-Path $checkout 'TASK.md'
    if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) { throw 'TASK.md missing' }
    $task = (Get-Content -LiteralPath $taskPath -Raw -Encoding UTF8).Trim()
    if ($task -ne 'Fix the bug described in ISSUE.md. Keep the change minimal. Run the existing tests.') {
        throw 'TASK.md differs from the benchmark protocol'
    }
    $env:GH_TOKEN = $null
    $env:GITHUB_TOKEN = $null

    $version = (& codex --version).Trim()
    Write-Host "Agent: $version; model: $Model; sandbox: workspace-write"
    Write-Host "Event log: $logPath"
    $task | & codex exec --ignore-user-config --ephemeral --json -C $checkout `
        -s workspace-write -m $Model -c 'model_reasoning_effort="medium"' `
        -c 'sandbox_workspace_write.network_access=false' - 2>&1 |
        Tee-Object -FilePath $logPath
    $agentExit = $LASTEXITCODE

    git -C $checkout add -A -- . ':(exclude,glob)build*/**' ':(exclude,glob)**/build*/**'
    if ($LASTEXITCODE -ne 0) { throw 'Could not stage agent changes' }
    git -C $checkout diff --cached --binary --no-ext-diff --output=$patchPath HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Could not save agent patch' }
    $hash = (Get-FileHash -LiteralPath $patchPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "Patch: $patchPath"
    Write-Host "SHA-256: $hash"
    if ($agentExit -ne 0) { throw "Codex CLI exited with code $agentExit; inspect event log" }
}
finally {
    $env:GH_TOKEN = $oldGhToken
    $env:GITHUB_TOKEN = $oldGithubToken
    $agentRootFull = [IO.Path]::GetFullPath($agentRoot).TrimEnd('\')
    $checkoutFull = [IO.Path]::GetFullPath($checkout)
    if (-not $checkoutFull.StartsWith("$agentRootFull\", [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Unsafe checkout cleanup path'
    }
    if (Test-Path -LiteralPath $checkoutFull) {
        Remove-Item -LiteralPath $checkoutFull -Recurse -Force
    }
}
