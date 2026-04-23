# Workflow: LinkedIn Job Search via MCP

## Objective
Use the LinkedIn MCP tool to search for job postings in the last 24 hours matching the candidate's background.

## MCP Tool
`search_linkedin_jobs` from the `@administrativetrick/linkedin-jobs-mcp` server (configured in `.claude/settings.json`).

## Search Queries
Run each query. Collect and deduplicate results by `job_id` across all calls.

| Keyword | Location | Date | Employment | Work | Salary |
|---------|----------|------|-----------|------|--------|
| Senior Data Engineer | Dallas, TX | 24hr | full-time | — | 120000 |
| Senior Data Engineer | Remote | 24hr | full-time | remote | 120000 |
| Data Architect | Dallas, TX | 24hr | full-time | — | 120000 |
| Data Architect | Remote | 24hr | full-time | remote | 120000 |
| Principal Engineer Data Platform | Remote | 24hr | full-time | — | 120000 |
| Engineering Manager Data | Remote | 24hr | full-time | — | 120000 |
| Distributed Systems Engineer | Remote | 24hr | full-time | — | 120000 |
| Staff Engineer Data | Remote | 24hr | full-time | — | 120000 |

**Note on salary filter**: The MCP supports salary up to "120000" as a minimum filter. The $200K hard requirement is enforced downstream in `tools/score_job_match.py` via LLM analysis of each job description.

## MCP Call Example
```
search_linkedin_jobs(
  keyword="Senior Data Engineer",
  location="Dallas, TX",
  dateSincePosted="24hr",
  jobType="full-time",
  remoteFilter="",
  salary="120000",
  limit=25
)
```

## After All Queries
1. Combine all results into one array
2. Deduplicate by `job_id` (or URL if no ID)
3. Pass the array to `tools/search_linkedin_jobs.py --jobs-json '<array>'` to normalise and write `.tmp/jobs_YYYYMMDD.json`

## Rate Limiting
- Add a short pause between MCP calls if making more than 4 in quick succession
- If the MCP returns an error mid-run: save results collected so far, log the error, continue with the pipeline
