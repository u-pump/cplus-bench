# Запуск агента владельцем

Агента запускает только владелец. Для Claude Code нужен **WSL2 Ubuntu**, причём репозиторий и временный checkout должны находиться в файловой системе Ubuntu (`~/...`), а не в `/mnt/c` или `/mnt/d`. Нативный Windows скрипт отклоняет. Скрипт берёт только приватный `u-pump/bench-in-<id>`, передаёт ему неизменённый `TASK.md`, сохраняет первую попытку и не даёт её перезаписать.

## Подготовка WSL2 один раз

В PowerShell Windows:

```powershell
wsl --install -d Ubuntu
wsl -l -v
```

Убедитесь, что у Ubuntu в последнем выводе версия **2**, затем откройте Ubuntu. В Ubuntu установите сборку, GitHub CLI, зависимости песочницы, Node/npm для фильтра seccomp и PowerShell 7 для запуска скрипта:

```bash
sudo apt-get update
sudo apt-get install -y git cmake ninja-build g++ gh bubblewrap socat curl wget apt-transport-https software-properties-common
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.8/install.sh | bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install 24
npm install -g @anthropic-ai/sandbox-runtime
source /etc/os-release
wget -q "https://packages.microsoft.com/config/ubuntu/$VERSION_ID/packages-microsoft-prod.deb"
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install -y powershell
```

Для Ubuntu 24.04 с `kernel.apparmor_restrict_unprivileged_userns=1` выполните шаг с профилем `bwrap` из [документации песочницы Claude Code](https://code.claude.com/docs/en/sandboxing#ubuntu-2404-and-later-allow-bubblewrap-to-create-user-namespaces) до запуска агента. Пакет [sandbox-runtime требует Node.js 22.12+](https://github.com/anthropics/sandbox-runtime/blob/main/package.json); команды выше устанавливают Node 24 через [nvm](https://github.com/nvm-sh/nvm). Скрипт проверяет WSL2, `bwrap`, `socat`, версию Node и наличие seccomp runtime; `sandbox.failIfUnavailable` закрывает оставшиеся ошибки инициализации без запуска команд вне песочницы.

Установите **Linux-версию** Claude Code и войдите в аккаунт; Windows-установка Claude не используется:

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude --version
claude auth login
claude auth status
gh auth login -h github.com
gh repo clone u-pump/cplus-bench ~/cplus-bench
cd ~/cplus-bench
git switch bench-10
```

`gh auth login` должен авторизовать владельца `u-pump`, имеющего доступ к приватному input-репозиторию. Эти установки и вход выполняются **до** прогона агента. Источники: [установка Claude Code](https://code.claude.com/docs/en/setup), [PowerShell для Ubuntu](https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu), [песочница Claude Code](https://code.claude.com/docs/en/sandboxing).

## Один кейс

Из `~/cplus-bench` в Ubuntu:

```bash
pwsh -NoProfile -File scripts/run-agent-local.ps1 -Agent claude-code fmt-4800
```

Скрипт запускает `claude -p` с `--restricted --safe-mode` и `--settings` JSON. Настройки включают sandbox, `failIfUnavailable`, автоматическое одобрение только sandboxed Bash, пустой `network.allowedDomains` со `strictAllowlist`, запрет `allowUnsandboxedCommands` и пустой `excludedCommands`. `--permission-prompts none` отклоняет оставшиеся запросы, а `--disallowedTools` закрывает `WebFetch` и `WebSearch`. Синтаксис подтверждён [настройками песочницы](https://code.claude.com/docs/en/sandboxing), [описанием settings](https://code.claude.com/docs/en/settings) и [CLI reference](https://code.claude.com/docs/en/cli-reference).

Патч пишется в `cases/<id>/agents/claude-code/agent-fix.patch` без `build*/`. `agent.yaml` содержит модель, версию, SHA-256, фактическую ОС/песочницу и `network_attempts` (число и короткие имена команд). Журнал остаётся в `.tmp/agent-runs/logs/`. Сбой CLI, отсутствие завершённой успешной Bash-команды и ошибка связи не меняют файлы попытки. После прогона владелец отправляет отдельный PR с патчем; вручную патч не правит и попытку не повторяет.

Для Codex CLI прежняя команда сохраняется: `pwsh -File scripts/run-agent-local.ps1 -Agent codex-cli <id>`.

**Граница изоляции:** встроенная песочница покрывает Bash и дочерние процессы. Сам процесс Claude Code, его файловые инструменты и возможные managed-настройки остаются вне этой границы; Bash по умолчанию может читать файлы хоста. `--restricted` ограничивает файловые инструменты рабочим каталогом, `--safe-mode` отключает память, `CLAUDE.md`, плагины, hooks и MCP, а seccomp закрывает обход WSL через запуск Windows-программ. Сетевые попытки выявляются по журналу; журнал не доказывает отсутствие всех попыток низкоуровневого соединения. Для строгой изоляции чтения хоста требуется отдельная VM или контейнер вокруг всего процесса Claude Code.
