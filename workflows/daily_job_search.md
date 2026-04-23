# Workflow: Daily Job Search and Application

## Objective
Each day, search LinkedIn for relevant job postings in the last 24 hours, score them against the master profile, and apply to strong matches. Log every application.

## Required Inputs
- `resume/my_profile.md` — master profile
- `.env` — LinkedIn credentials + OpenRouter API key
- `applied/index.json` — deduplication index

## Steps

### 1. Search LinkedIn via MCP
Call the LinkedIn MCP tool `search_linkedin_jobs` for each query in `workflows/linkedin_search.md`.

Collect all results, deduplicate by `job_id`, then save to `.tmp/jobs_YYYYMMDD.json` by running:
```
python tools/search_linkedin_jobs.py --jobs-json '<json_array>' --date YYYYMMDD
```

On MCP failure (timeout, no results, error): log to `.tmp/errors_YYYYMMDD.log` and abort.

### 2. Deduplicate
Check `applied/index.json` and filter out any job IDs already processed.

### 3. Score Each Job
Run `python tools/score_job_match.py --jobs-file .tmp/jobs_YYYYMMDD.json --date YYYYMMDD`

- Enriches each job with `match_score` (0–100) and `match_reason`
- Hard gate: any job with stated salary < $200K is scored 0 automatically
- Only jobs scoring **≥ 85** proceed to application
- Full scored list (including non-matches) saved to `.tmp/scored_YYYYMMDD.json`

### 4. Apply to Matches (cap: 10 per day)
Run `python tools/run_daily.py --skip-search --date YYYYMMDD`

This handles: tailor → generate PDF → apply → log for each match.

Alternatively, step through manually:

For each matched job (sorted descending by score, max 10):

  a. `python tools/tailor_resume.py --job-id <id> --date YYYYMMDD`
  b. `python tools/generate_pdf.py --job-id <id> --company "..." --title "..." --date YYYYMMDD`
  c. Apply:
     - Easy Apply: `python tools/apply_linkedin_easy.py --job-id <id> --resume-pdf <path>`
     - External: `python tools/apply_external.py --url <url> --resume-pdf <path>`
  d. `python tools/log_application.py --job-id <id> ...`

### 5. Log Skipped Jobs
For jobs that scored ≥85 but were skipped due to the daily cap:
- Run `tools/log_application.py` with `status = "capped_skipped"`
- These will NOT be in `applied/index.json` so they will be reconsidered tomorrow

## Edge Cases
- **MCP returns no jobs**: Normal outcome; log empty run to `.tmp/errors_YYYYMMDD.log`
- **Salary < $200K stated in JD**: Scored 0 automatically — never applied to
- **PDF generation failure**: Skip application for that job, log error, move to next
- **External apply returns `manual_required`**: Log with that status; do not retry
- **Rate limit on OpenRouter**: Wait 10 seconds, retry once; if it fails again, skip that job

## Expected Outputs
- `.tmp/jobs_YYYYMMDD.json` — raw job list from MCP
- `.tmp/scored_YYYYMMDD.json` — scored job list (all jobs including non-matches)
- `resume/versions/resume_{Company}_{Role}_{YYYYMMDD}.pdf` — one PDF per application
- `applied/YYYYMMDD_{Company}_{Role}.md` — one note per application
- `applied/index.json` — updated with today's applications
