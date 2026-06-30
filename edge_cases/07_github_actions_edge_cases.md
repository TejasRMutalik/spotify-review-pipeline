# Edge Cases: GitHub Actions Workflow (`.github/workflows/scrape.yml`)

## EC-GA-01: Required GitHub Secret Not Set
**Risk**: If a developer forks the repo and pushes without adding the 5 required GitHub Secrets, the workflow runs but hits cryptic errors deep in the pipeline.

**Handle**: `main.py` calls `validate_environment()` as the very first step. It checks for all required env vars and exits with code 1 immediately if any are missing — the error message clearly lists which secrets are absent. The Actions run is marked ❌ with a readable log.

---

## EC-GA-02: Base64 Decode of Service Account Fails
**Risk**: If `GOOGLE_SERVICE_ACCOUNT_B64` was set incorrectly (e.g., copied with newlines, or not base64-encoded at all), the `base64 -d` command silently writes a malformed file. The uploader then fails with a JSON parse error.

**Handle**:
- The decode step should include a validation:
  ```bash
  echo "${{ secrets.GOOGLE_SERVICE_ACCOUNT_B64 }}" | base64 -d > /tmp/service_account.json
  python -c "import json; json.load(open('/tmp/service_account.json'))" || exit 1
  ```
- The `FileNotFoundError` / `JSONDecodeError` propagates to `main.py` and marks the run ❌.

---

## EC-GA-03: Workflow Runs Longer Than 60 Minutes (Timeout)
**Risk**: If a scraper hangs (e.g., PRAW is waiting forever on a rate-limit, or the App Store scraper loops), the GitHub Actions job runs indefinitely and wastes runner minutes.

**Handle**: `timeout-minutes: 60` is set on the job. GitHub Actions kills the job and marks it ❌ after 60 minutes.

---

## EC-GA-04: Cron Schedule Skipped by GitHub (Inactive Repo)
**Risk**: GitHub Actions **automatically disables scheduled workflows** on repos with no activity for 60 days. The cron stops firing silently.

**Handle**: This is a GitHub platform behaviour. Document it in the README. To re-enable: go to Actions tab → find the disabled workflow → click "Enable workflow". Alternatively, make occasional commits or use `workflow_dispatch` to keep it active.

---

## EC-GA-05: Concurrent Workflow Runs (Two Triggers at Once)
**Risk**: If the cron fires at the same time a manual `workflow_dispatch` is triggered, two runs may simultaneously clear and write to the same Google Sheet, causing race conditions and corrupted data.

**Handle**: Add concurrency control to the workflow:
```yaml
concurrency:
  group: scrape-pipeline
  cancel-in-progress: true   # newer run cancels the older one
```

---

## EC-GA-06: GitHub Runner Runs Out of Memory
**Risk**: The GitHub Actions free tier provides ~7GB RAM. Concatenating 5000 reviews with long text into a DataFrame is well within limits, but future scaling could push this.

**Handle**: At current data volumes (~5000 rows × 10 cols), memory usage is negligible. For future scale, add chunked processing in `cleaner.py`. Add `timeout-minutes: 60` (already in the workflow) as a backstop.

---

## EC-GA-07: Credentials Left in Runner Environment After Failure
**Risk**: If a step fails before the credential cleanup step, `/tmp/service_account.json` remains in the ephemeral runner. The runner is destroyed after the job, so this is low-risk, but defence-in-depth is good practice.

**Handle**: The cleanup step uses `if: always()`:
```yaml
- name: Clean up credentials
  if: always()
  run: rm -f /tmp/service_account.json
```
This runs regardless of whether previous steps succeeded or failed.

---

## EC-GA-08: `requirements.txt` Has a Version Conflict
**Risk**: A pinned dependency (e.g., `google-auth==2.29.0`) may conflict with a transitive dependency introduced by another library update.

**Handle**: All versions are pinned in `requirements.txt`. If a conflict arises, the `pip install` step will fail with a clear error. Resolution: update the conflicting pin. Consider adding `pip check` as a workflow step to catch this early.

---

## EC-GA-09: Workflow File Has YAML Syntax Error
**Risk**: A mis-indented `scrape.yml` silently fails or causes GitHub to not register the workflow at all.

**Handle**: Validate YAML locally before pushing:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/scrape.yml'))"
```
Or use the `actionlint` CLI tool for GitHub Actions-specific validation.
