function ConvertFrom-ClaudeEvents {
    param([Parameter(Mandatory)][string]$Log)
    @($Log -split "`r?`n" | Where-Object { $_.TrimStart().StartsWith('{') } | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $null -ne $_ })
}

function Get-ClaudeResultText {
    param($Content)
    if ($Content -is [string]) { return $Content }
    return (@($Content | ForEach-Object { if ($_.text) { [string]$_.text } }) -join "`n")
}

function Get-ClaudeEvidence {
    param([Parameter(Mandatory)][string]$Log)
    $events = @(ConvertFrom-ClaudeEvents -Log $Log)
    $init = $events | Where-Object { $_.type -eq 'system' -and $_.subtype -eq 'init' } | Select-Object -First 1
    $result = $events | Where-Object { $_.type -eq 'result' } | Select-Object -Last 1
    $bashIds = @($events | Where-Object { $_.type -eq 'assistant' } | ForEach-Object {
        $_.message.content | Where-Object { $_.type -eq 'tool_use' -and $_.name -eq 'Bash' } | ForEach-Object { $_.id }
    })
    $successfulBash = @($events | Where-Object { $_.type -eq 'user' } | ForEach-Object {
        $_.message.content | Where-Object {
            $_.type -eq 'tool_result' -and $_.tool_use_id -in $bashIds -and -not $_.is_error -and
            (((Get-ClaudeResultText $_.content) -match '(?im)(?:^|\n)\s*(?:Exit code|Process exited with code|Command exited with code)\s*:?\s*0\b') -or
             $_.exitCode -eq 0)
        }
    })
    if (-not $init.model -or -not $result -or $result.is_error -or
        $result.subtype -ne 'success' -or $successfulBash.Count -eq 0) {
        throw 'Claude Code did not complete a successful Bash command; attempt not recorded'
    }
    return [string]$init.model
}

function Get-ClaudeNetworkAttempts {
    param([Parameter(Mandatory)][string]$Log)
    $events = @(ConvertFrom-ClaudeEvents -Log $Log)
    $labels = [System.Collections.Generic.List[string]]::new()
    $networkTools = @{}
    foreach ($event in $events) {
        if ($event.type -ne 'assistant') { continue }
        foreach ($block in @($event.message.content)) {
            if ($block.type -ne 'tool_use') { continue }
            $label = $null
            if ($block.name -in @('WebFetch', 'WebSearch')) {
                $label = [string]$block.name
            } elseif ($block.name -eq 'Bash') {
                $command = [string]$block.input.command
                if ($command -match '(?i)(?:^|[;&|\s])curl(?:\s|$)') { $label = 'curl' }
                elseif ($command -match '(?i)(?:^|[;&|\s])wget(?:\s|$)') { $label = 'wget' }
                elseif ($command -match '(?i)\bgit\b[^;&|\n]{0,120}\b(clone|fetch|pull|submodule)\b') { $label = "git $($Matches[1].ToLowerInvariant())" }
                elseif ($command -match '(?i)(?:^|[;&|\s/])gh(?:\s|$)') { $label = 'gh' }
                elseif ($command -match '(?i)\b(?:pip|pip3)\s+install\b') { $label = 'pip install' }
                elseif ($command -match '(?i)\bnpm\s+(?:install|ci)\b') { $label = 'npm install' }
                elseif ($command -match '(?i)\bcargo\s+(?:install|fetch)\b') { $label = 'cargo fetch/install' }
                elseif ($command -match '(?i)\b(?:apt|apt-get)\s+install\b') { $label = 'apt install' }
            }
            if ($label) {
                $labels.Add($label)
                if ($block.id) { $networkTools[[string]$block.id] = $true }
            }
        }
    }
    foreach ($event in $events) {
        if ($event.type -ne 'user') { continue }
        foreach ($block in @($event.message.content)) {
            if ($block.type -ne 'tool_result' -or $networkTools.ContainsKey([string]$block.tool_use_id)) { continue }
            if ((Get-ClaudeResultText $block.content) -match '(?i)host_not_allowed|network (?:is )?unreachable|network access (?:is )?denied|connection (?:refused|timed out)|could not resolve host|sandbox.*network') {
                $labels.Add('network error')
            }
        }
    }
    return [ordered]@{ count = $labels.Count; commands = @($labels | Select-Object -Unique) }
}

function Get-AgentCheckoutRoot {
    param([Parameter(Mandatory)][string]$Agent, [Parameter(Mandatory)][string]$BenchmarkRoot)
    if ($Agent -eq 'claude-code') { return "/var/tmp/cplus-bench-agent/$Agent" }
    return (Join-Path (Split-Path -Parent $BenchmarkRoot) ".tmp/bench-agent/$Agent")
}

function New-ClaudeSettings {
    # Read rules also cover Grep/Glob; Edit rules also cover Write.
    # Write(path) and Glob(path) rules are accepted by Claude but never match.
    $deniedTools = @(
        'Read(~/)', 'Read(~/**)', 'Read(//mnt)', 'Read(//mnt/**)',
        'Edit(~/)', 'Edit(~/**)', 'Edit(//mnt)', 'Edit(//mnt/**)'
    )
    $settings = [ordered]@{
        permissions = [ordered]@{
            blockReadsOutsideWorkingDirectories = $true
            deny = $deniedTools
        }
        sandbox = [ordered]@{
            enabled = $true
            failIfUnavailable = $true
            autoAllowBashIfSandboxed = $true
            allowUnsandboxedCommands = $false
            excludedCommands = @()
            filesystem = [ordered]@{
                disabled = $false
                denyRead = @('~/', '/mnt')
                allowRead = @('.')
            }
            network = [ordered]@{
                allowedDomains = @()
                strictAllowlist = $true
            }
        }
    }
    return ($settings | ConvertTo-Json -Depth 8 -Compress)
}

function Assert-ClaudeSettingsPolicy {
    param([Parameter(Mandatory)][string]$SettingsJson)
    $settings = $SettingsJson | ConvertFrom-Json
    $fs = $settings.sandbox.filesystem
    $neededRules = @(
        'Read(~/)', 'Read(~/**)', 'Read(//mnt)', 'Read(//mnt/**)',
        'Edit(~/)', 'Edit(~/**)', 'Edit(//mnt)', 'Edit(//mnt/**)'
    )
    if (-not $settings.sandbox.enabled -or -not $settings.sandbox.failIfUnavailable -or
        $settings.sandbox.allowUnsandboxedCommands -or -not $settings.permissions.blockReadsOutsideWorkingDirectories -or
        $fs.disabled -or
        @($fs.denyRead).Count -ne 2 -or $fs.denyRead -notcontains '~/' -or $fs.denyRead -notcontains '/mnt' -or
        @($fs.allowRead).Count -ne 1 -or $fs.allowRead[0] -ne '.' -or
        @($settings.sandbox.network.allowedDomains).Count -ne 0 -or -not $settings.sandbox.network.strictAllowlist) {
        throw 'Настройки песочницы Claude не запрещают чтение домашней папки и /mnt.'
    }
    foreach ($rule in $neededRules) {
        if ($settings.permissions.deny -notcontains $rule) {
            throw "Нет правила permissions.deny: $rule"
        }
    }
}

function Assert-ClaudeSettingsIsolation {
    param([Parameter(Mandatory)][string]$SettingsJson, [Parameter(Mandatory)][string]$Checkout)
    Assert-ClaudeSettingsPolicy -SettingsJson $SettingsJson
    if (-not $IsLinux) { throw 'Проверка изоляции Claude требует WSL2 Ubuntu.' }
    $resolved = (& realpath -- $Checkout).TrimEnd('/')
    if ($LASTEXITCODE -ne 0 -or -not $resolved.StartsWith('/var/tmp/cplus-bench-agent/')) {
        throw 'Checkout Claude должен находиться в /var/tmp/cplus-bench-agent/.'
    }
    $homePath = (& realpath -- $env:HOME).TrimEnd('/')
    if ($resolved -eq $homePath -or $resolved.StartsWith("$homePath/") -or
        $resolved -eq '/mnt' -or $resolved.StartsWith('/mnt/')) {
        throw 'Checkout Claude оказался внутри домашней папки или /mnt.'
    }
}

function Assert-ClaudeSandboxHost {
    $release = if (Test-Path -LiteralPath '/proc/sys/kernel/osrelease') {
        Get-Content -LiteralPath '/proc/sys/kernel/osrelease' -Raw
    } else { '' }
    if (-not $IsLinux -or $release -notmatch '(?i)microsoft.*wsl2|wsl2.*microsoft') {
        throw 'Claude Code запускается только в WSL2 Ubuntu с песочницей. Установите WSL2 Ubuntu и выполните инструкцию docs/run-agent.md.'
    }
    foreach ($name in @('bwrap', 'socat', 'node', 'npm')) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
            throw "Песочница Claude Code недоступна: нет $name. Установите bubblewrap, socat и @anthropic-ai/sandbox-runtime по docs/run-agent.md."
        }
    }
    try { $nodeVersion = [version]((& node --version).Trim().TrimStart('v')) }
    catch { throw 'Для фильтра seccomp нужен Node.js 22.12+; см. docs/run-agent.md.' }
    if ($nodeVersion -lt [version]'22.12.0') {
        throw 'Для фильтра seccomp нужен Node.js 22.12+; см. docs/run-agent.md.'
    }
    $npmRoot = (& npm root -g).Trim()
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $npmRoot '@anthropic-ai/sandbox-runtime'))) {
        throw 'Для WSL2 нужен фильтр seccomp: npm install -g @anthropic-ai/sandbox-runtime. См. docs/run-agent.md.'
    }
}
