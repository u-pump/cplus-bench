# Owner setup for verification

The repository is safe to browse before this setup. Empty `agent-fix.patch` files produce `PENDING`; no AI agent has run.

1. On GitHub, open your profile picture → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**. Set **Resource owner** to `u-pump`, **Repository access** to **Only select repositories**, and select only `u-pump/c-plus`. Under **Repository permissions**, set **Contents: Read-only** and leave other configurable permissions unset. Choose a short expiry, generate the token, and complete any organization approval required for private-repository access. The automatic Metadata read permission is normal.
2. In `u-pump/cplus-bench`, open **Settings** → **Secrets and variables** → **Actions** → **Secrets** → **New repository secret**. Name it `CPLUS_READ_TOKEN` and paste the token value. Do not place it in a file, issue, commit, or workflow input.
3. In `u-pump/cplus-bench`, open **Settings** → **Actions** → **General** → **Approval for running fork pull request workflows from contributors**. Select **Require approval for all external contributors** (the current GitHub wording for the requested outside-collaborator protection), then **Save**. The workflow itself has no `pull_request` or `pull_request_target` trigger.
4. If the organization policy permits it, leave Actions enabled and permit `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, and `actions/download-artifact`. When an agent patch has been submitted by the owner, push its unchanged file under `cases/` or run **Actions** → **Verify submitted patches** → **Run workflow** with its case ID. Review the generated report before making any benchmark claim.

The read-only token is used only in the install step. The separate publish job receives the standard `GITHUB_TOKEN` with `contents: write` to commit the public summary. The verification job receives `contents: read` only.
