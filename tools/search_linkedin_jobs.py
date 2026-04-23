"""
Save LinkedIn job search results to .tmp/jobs_YYYYMMDD.json.

In normal daily operation this file is NOT called directly — Claude calls the
LinkedIn MCP tool (search_linkedin_jobs) for each query, collects results,
deduplicates by job_id, and writes them here.

This script exists as a utility to save pre-fetched job data from stdin or a
JSON argument, and to normalise the schema the rest of the pipeline expects.

Usage (agent writes collected MCP results):
  python tools/search_linkedin_jobs.py --jobs-json '[{...}, ...]' --date 20260422

Usage (pipe from another source):
  echo '[{...}]' | python tools/search_linkedin_jobs.py --date 20260422
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

TMP_DIR = Path(".tmp")
TMP_DIR.mkdir(exist_ok=True)

REQUIRED_FIELDS = {"job_id", "title", "company", "jd_text"}


def normalise(job: dict) -> dict:
    """Ensure the job dict has all fields the pipeline expects."""
    return {
        "job_id": str(job.get("job_id") or job.get("id") or ""),
        "title": job.get("title") or job.get("position") or "",
        "company": job.get("company") or job.get("companyName") or "",
        "location": job.get("location") or "",
        "apply_type": job.get("apply_type") or ("easy_apply" if job.get("easyApply") else "external"),
        "apply_url": job.get("apply_url") or job.get("applyUrl") or job.get("jobUrl") or "",
        "jd_text": job.get("jd_text") or job.get("description") or job.get("jobDescription") or "",
        "posted_date": job.get("posted_date") or job.get("postedAt") or job.get("date") or "",
        "search_query": job.get("search_query") or "",
        "salary": job.get("salary") or job.get("salaryRange") or "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs-json", help="JSON array of job objects as a string")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()

    if args.jobs_json:
        raw = json.loads(args.jobs_json)
    elif not sys.stdin.isatty():
        raw = json.load(sys.stdin)
    else:
        print("ERROR: Provide --jobs-json or pipe JSON via stdin")
        raise SystemExit(1)

    jobs = [normalise(j) for j in raw]

    # Deduplicate by job_id
    seen: set[str] = set()
    unique = []
    for job in jobs:
        jid = job["job_id"]
        if jid and jid not in seen:
            seen.add(jid)
            unique.append(job)

    # Drop entries missing critical fields
    valid = [j for j in unique if j["job_id"] and j["title"] and j["jd_text"]]

    out_path = TMP_DIR / f"jobs_{args.date}.json"
    with open(out_path, "w") as f:
        json.dump(valid, f, indent=2)

    print(f"Saved {len(valid)} unique jobs to {out_path}")


if __name__ == "__main__":
    main()
