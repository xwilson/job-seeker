# Workflow: Job Matching and Scoring

## Objective
Use an LLM to score each job against the candidate's master profile. Only jobs scoring ≥70 are forwarded for application.

## Model
OpenRouter API → `anthropic/claude-opus-4-7`

## Scoring Dimensions (total: 100 points)

| Dimension | Points | Description |
|-----------|--------|-------------|
| Role seniority | 25 | Matches senior IC, architect, or manager level (not junior, not VP+) |
| Tech stack overlap | 30 | Java, Python, Spark, Kafka, AWS, distributed systems, Kubernetes |
| Domain fit | 20 | Data platforms, fintech, enterprise scale, streaming/batch pipelines |
| Company quality | 15 | Established tech org, stable company, not obvious culture mismatch |
| Location/remote fit | 10 | Dallas TX on-site, hybrid, or fully remote |

## System Prompt (used for all scoring calls)
```
You are a job matching assistant. You score job postings against a candidate profile.

Candidate Profile:
{master_profile_contents}

Scoring criteria:
- Role seniority (25 pts): Must be senior IC (Staff/Principal/Senior), architect, or engineering manager level. Not junior. Not C-suite or VP.
- Tech stack overlap (30 pts): Award points proportionally to how many of these appear in the JD: Java, Python, Spark, Kafka, AWS, Kubernetes, distributed systems, streaming, batch pipelines, data platforms.
- Domain fit (20 pts): Financial services, enterprise data platforms, large-scale systems preferred.
- Company quality (15 pts): Stable, established company. Deduct points for vague job descriptions, obvious startups with no traction, or misaligned culture signals.
- Location fit (10 pts): Full points for remote or Dallas TX. Partial for hybrid in Dallas area. Zero for required relocation to other cities.

Return ONLY valid JSON:
{"match_score": <integer 0-100>, "match_reason": "<one sentence explaining the score>"}
```

## Threshold
- **≥ 70**: Forward for application
- **< 70**: Skip; record in scored list for audit

## Edge Cases
- JD text is very short or garbled: score 0, reason "insufficient job description"
- Role is clearly a different field (e.g., marketing, sales, finance): score 0 immediately without calling LLM
- Duplicate job ID already in `applied/index.json`: skip without scoring
