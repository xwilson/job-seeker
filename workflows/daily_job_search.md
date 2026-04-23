# Workflow: Daily Job Search and Application

## Objective
Each day, search LinkedIn for relevant job postings in the last 24 hours, score them against the master profile, and apply to strong matches. Log every application.

## Required Inputs
- `resume/my_profile.md` — master profile
- `.env` — LinkedIn credentials + OpenRouter API key
- `applied/index.json` — deduplication index

## Steps

### 1. Search LinkedIn
Run `tools/search_linkedin_jobs.py`
- Searches for jobs posted in the last 24 hours
- Returns `.tmp/jobs_YYYYMMDD.json` with raw job listings
- On failure (login challenge, network error): abort and note the error; do not proceed

### 2. Deduplicate
Run `tools/check_already_applied.py`
- Loads `applied/index.json`
- Returns the set of job IDs already processed
- Filter these out of the jobs list before scoring

### 3. Score Each Job
For each remaining job, run `tools/score_job_match.py`
- Enriches each job with `match_score` (0–100) and `match_reason`
- Only pass jobs with score ≥ 70 to the next step
- Save full scored list (including non-matches) to `.tmp/scored_YYYYMMDD.json` for audit

### 4. Apply to Matches (cap: 10 per day)
For each matched job (sorted descending by score, max 10):

  a. Run `tools/tailor_resume.py` — generates tailored resume + cover letter markdown
  b. Run `tools/generate_pdf.py` — creates PDF at `resume/versions/resume_{Company}_{Role}_{YYYYMMDD}.pdf`
  c. Determine apply path:
     - If `apply_type == "easy_apply"`: run `tools/apply_linkedin_easy.py`
     - If `apply_type == "external"`: run `tools/apply_external.py`
  d. Run `tools/log_application.py` — write note to `applied/` and update `applied/index.json`

### 5. Log Skipped Jobs
For jobs that scored ≥70 but were skipped due to the daily cap:
- Run `tools/log_application.py` with `status = "capped_skipped"`
- These will NOT be in `applied/index.json` so they will be reconsidered tomorrow

## Edge Cases
- **LinkedIn login challenge or CAPTCHA**: Abort immediately, log error to `.tmp/errors_YYYYMMDD.log`
- **No jobs found**: Normal outcome; log empty run to `.tmp/errors_YYYYMMDD.log`
- **PDF generation failure**: Skip application for that job, log error, move to next
- **External apply returns `manual_required`**: Log with that status; do not retry
- **Rate limit or timeout on OpenRouter**: Wait 10 seconds, retry once; if it fails again, skip that job and continue

## Expected Outputs
- `.tmp/jobs_YYYYMMDD.json` — raw job list
- `.tmp/scored_YYYYMMDD.json` — scored job list (all jobs including non-matches)
- `resume/versions/resume_{Company}_{Role}_{YYYYMMDD}.pdf` — one PDF per application
- `applied/YYYYMMDD_{Company}_{Role}.md` — one note per application
- `applied/index.json` — updated with today's applications
