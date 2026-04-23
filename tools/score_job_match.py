"""
Score a job against the master profile using OpenRouter (claude-opus-4-7).
Outputs enriched job JSON with match_score and match_reason.

Usage:
  python tools/score_job_match.py --jobs-file .tmp/jobs_20260422.json --date 20260422
  python tools/score_job_match.py --job-id 1234567 --date 20260422
"""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROFILE_PATH = Path("resume/my_profile.md")
TMP_DIR = Path(".tmp")
MODEL = "anthropic/claude-opus-4-7"
SCORE_THRESHOLD = 70

# Domains that are clearly not relevant — skip LLM call immediately
IRRELEVANT_KEYWORDS = [
    "marketing manager", "sales manager", "account executive", "finance director",
    "hr manager", "recruiter", "creative director", "graphic designer",
]


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set in .env")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def load_profile() -> str:
    return PROFILE_PATH.read_text(encoding="utf-8")


def is_irrelevant(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in IRRELEVANT_KEYWORDS)


def score_job(client: OpenAI, profile: str, job: dict) -> dict:
    title = job.get("title", "")
    jd_text = job.get("jd_text", "").strip()

    if is_irrelevant(title):
        job["match_score"] = 0
        job["match_reason"] = "Role is clearly outside candidate's domain"
        return job

    if len(jd_text) < 100:
        job["match_score"] = 0
        job["match_reason"] = "Insufficient job description text"
        return job

    system_prompt = f"""You are a job matching assistant. Score job postings against a candidate profile.

Scoring criteria (total 100 points):
- Role seniority (25 pts): Senior IC (Staff/Principal/Senior), architect, or engineering manager. Not junior, not C-suite/VP.
- Tech stack overlap (30 pts): Proportional to matches among: Java, Python, Spark, Kafka, AWS, Kubernetes, distributed systems, streaming, batch pipelines, data platforms.
- Domain fit (20 pts): Financial services, enterprise data platforms, large-scale systems preferred.
- Company quality (15 pts): Stable company, clear role, reasonable culture signals.
- Location fit (10 pts): Full points for remote or Dallas TX. Partial for hybrid Dallas area. Zero for required relocation.

Return ONLY valid JSON on a single line:
{{"match_score": <integer 0-100>, "match_reason": "<one sentence explaining the score>"}}

Candidate Profile:
{profile}"""

    user_prompt = f"""Job Title: {title}
Company: {job.get("company", "")}
Location: {job.get("location", "")}

Job Description:
{jd_text[:4000]}"""

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            job["match_score"] = int(result.get("match_score", 0))
            job["match_reason"] = result.get("match_reason", "")
            return job
        except json.JSONDecodeError:
            job["match_score"] = 0
            job["match_reason"] = "LLM returned unparseable response"
            return job
        except Exception as e:
            if attempt == 0:
                print(f"  Retrying after error: {e}")
                time.sleep(10)
            else:
                job["match_score"] = 0
                job["match_reason"] = f"Scoring error: {e}"
    return job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs-file", help="Path to jobs JSON file")
    parser.add_argument("--job-id", help="Score a single job ID from today's jobs file")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    from datetime import datetime
    date_str = args.date or datetime.now().strftime("%Y%m%d")

    if args.jobs_file:
        jobs_path = Path(args.jobs_file)
    else:
        jobs_path = TMP_DIR / f"jobs_{date_str}.json"

    if not jobs_path.exists():
        print(f"ERROR: Jobs file not found: {jobs_path}")
        raise SystemExit(1)

    with open(jobs_path) as f:
        jobs = json.load(f)

    if args.job_id:
        jobs = [j for j in jobs if j.get("job_id") == args.job_id]
        if not jobs:
            print(f"ERROR: job_id {args.job_id} not found in {jobs_path}")
            raise SystemExit(1)

    client = get_client()
    profile = load_profile()
    print(f"Scoring {len(jobs)} jobs...")

    for job in jobs:
        score_job(client, profile, job)
        score = job["match_score"]
        indicator = "✓" if score >= SCORE_THRESHOLD else "✗"
        print(f"  {indicator} {job.get('title')} at {job.get('company')} — score: {score} — {job.get('match_reason')}")

    out_path = TMP_DIR / f"scored_{date_str}.json"
    with open(out_path, "w") as f:
        json.dump(jobs, f, indent=2)
    print(f"\nScored results saved to {out_path}")

    matches = [j for j in jobs if j.get("match_score", 0) >= SCORE_THRESHOLD]
    print(f"Matches (score ≥ {SCORE_THRESHOLD}): {len(matches)}/{len(jobs)}")
    return matches


if __name__ == "__main__":
    main()
