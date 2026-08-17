# PT-006: Missing Required Status Checks — PR #9 Merged Despite Failed Lint

**Date:** 2026-08-16  
**Status:** Open — awaiting branch protection update  
**Related PR:** #9 (feature/design-system)

## Problem
PR #9 was merged despite having a failed `Lint (ruff)` check. The lint failure was caused by `docs/ui-ux-spec.md` containing Python code blocks with single quotes that ruff wanted to convert to double quotes. The fix was applied in PR #10 via `pyproject.toml` `[tool.ruff.format] exclude = ["**/*.md"]`.

This indicates a systematic gap: the `main` branch does not require status checks to pass before merging, allowing broken code to be merged.

## Root Cause
1. **No required status checks:** The `main` branch protection rules do not have "Require status checks to pass before merging" enabled.
2. **No required reviews:** Pull request reviews are not enforced before merging.
3. **Human error:** The merge was performed manually without verifying CI status.

## Fix Required
1. **Enable required status checks** on `main` branch protection:
   - `Lint (ruff)`
   - `Tests`
   - `Docker Build`
   - `PGAI capability (non-blocking)`
2. **Enable required reviews:** 1 approving review, dismiss stale.
3. **Enforce for administrators.**
4. **Require conversation resolution.**

Can be applied via GitHub UI (Settings → Branches → Branch protection rules → Edit `main`) or via:
```bash
gh api repos/satishsurath/summarizeme.runningdigitally.com/branches/main/protection \
  -X PATCH \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  --input /tmp/branch-protection.json
```

## Verification
- Create a test PR with a failing check → merge should be blocked.
- Verify all existing PRs (2-10) have passing checks before merging.

## Related
- PR #9: https://github.com/satishsurath/summarizeme.runningdigitally.com/pull/9
- PR #10 (lint fix): https://github.com/satishsurath/summarizeme.runningdigitally.com/pull/10
- Code Review Sweep: 9 agents reviewed PRs 2-10, found XSS, dead code, and quality issues — all fixed in current branch.
