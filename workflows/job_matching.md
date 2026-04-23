# Workflow: Job Matching and Scoring

## Objective
Use an LLM to score each job against the candidate's master profile. Only jobs scoring **≥ 85** are forwarded for application.

## Model
OpenRouter API → `anthropic/claude-opus-4-7`

## Hard Gate — $200K Minimum Compensation
**Before scoring**, check if the job description or salary field explicitly states compensation below $200,000/year.
- If yes: score = 0, reason = "Salary below $200K threshold" — skip immediately, do not call LLM
- This check is implemented in `tools/score_job_match.py` via `_explicit_low_salary()`

## Scoring Dimensions (total: 100 points)

| Dimension | Points | Description |
|-----------|--------|-------------|
| Role seniority | 20 | Senior IC (Staff/Principal/Senior), architect, or manager level |
| Tech stack overlap | 25 | Java, Python, Spark, Kafka, AWS, Kubernetes, distributed systems, streaming, data platforms |
| Domain fit | 15 | Data platforms, fintech, enterprise scale, streaming/batch pipelines |
| Company quality | 10 | Established tech org, stable company, not obvious culture mismatch |
| Location/remote fit | 10 | Dallas TX on-site, hybrid, or fully remote |
| Compensation signals | 20 | Does this role credibly pay ≥$200K total comp? (see below) |

### Compensation Signals Scoring (20 pts)
- **20 pts**: Salary explicitly stated ≥$200K, OR FAANG/top-tier finance firm at Staff+/Architect/Manager level
- **10 pts**: Large enterprise or established tech company at senior level; salary not stated but role type typically pays $200K+
- **0 pts**: Salary stated below $200K; OR startup/small company where compensation signals are weak

## Threshold
- **≥ 85**: Forward for application
- **< 85**: Skip; record in scored list for audit

## Edge Cases
- JD text is very short or garbled: score 0, reason "insufficient job description"
- Role is clearly a different field (marketing, sales, HR, etc.): score 0 without LLM call
- Duplicate job ID already in `applied/index.json`: skip without scoring
- Role is at a very small or unknown company with no salary info: score compensation signals at 5/20 maximum
