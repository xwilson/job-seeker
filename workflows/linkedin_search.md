# Workflow: LinkedIn Job Search

## Objective
Search LinkedIn for job postings in the last 24 hours that match the candidate's background in senior data engineering, distributed systems, and platform architecture.

## Search Queries
Run each query sequentially. Deduplicate results by job ID before returning.

1. `"Senior Data Engineer"` — Dallas, TX + Remote
2. `"Data Architect"` — Dallas, TX + Remote
3. `"Principal Engineer Data Platform"` — Dallas, TX + Remote
4. `"Engineering Manager Data"` — Dallas, TX + Remote
5. `"Distributed Systems Engineer"` — Dallas, TX + Remote
6. `"Staff Engineer Data"` — Dallas, TX + Remote

## Filters
- **Date posted**: Last 24 hours
- **Location**: Dallas, TX OR Remote
- **Experience level**: Mid-Senior, Director (exclude Entry, Internship)

## Session Management
- Browser session stored at `.tmp/linkedin_session/`
- On first run or expired session: log in using `LINKEDIN_EMAIL` + `LINKEDIN_PASSWORD` from `.env`
- If login requires 2FA or CAPTCHA: abort; log to `.tmp/errors_YYYYMMDD.log`; do not attempt automated bypass
- After successful login, session cookies are persisted automatically

## Data to Extract Per Job
```json
{
  "job_id": "string (LinkedIn job ID from URL)",
  "title": "string",
  "company": "string",
  "location": "string",
  "apply_type": "easy_apply | external",
  "apply_url": "string (LinkedIn URL for easy_apply, external URL for external)",
  "jd_text": "string (full job description text)",
  "posted_date": "string (ISO 8601 or relative like '12 hours ago')"
}
```

## Rate Limiting
- Add a random 1–3 second delay between page loads
- Do not run more than 6 search queries per session
- If LinkedIn shows a security challenge mid-session: stop, save what was collected so far, log the error

## Output
`.tmp/jobs_YYYYMMDD.json` — array of job objects
