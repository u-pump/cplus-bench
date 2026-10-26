function Get-ClaudeEvidence {
    param([Parameter(Mandatory)][string]$Log)
    $events = @($Log -split "`r?`n" | Where-Object { $_.TrimStart().StartsWith('{') } | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $null -ne $_ })
    $init = $events | Where-Object { $_.type -eq 'system' -and $_.subtype -eq 'init' } | Select-Object -First 1
    $result = $events | Where-Object { $_.type -eq 'result' } | Select-Object -Last 1
    $completedActions = @($events | Where-Object { $_.type -eq 'user' } | ForEach-Object {
        $_.message.content | Where-Object { $_.type -eq 'tool_result' -and -not $_.is_error }
    })
    if (-not $init.model -or -not $result -or $result.is_error -or $result.subtype -ne 'success' -or $completedActions.Count -eq 0) {
        throw 'Claude Code did not complete with tool actions; attempt not recorded'
    }
    return [string]$init.model
}
