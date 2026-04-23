"""
Main daily orchestration script. Runs the full pipeline:
  1. Search LinkedIn for today's jobs
  2. Deduplicate against applied/index.json
  3. Score each job
  4. Apply to matches (cap: 10 per day)
  5. Log every result

Usage:
  python tools/run_daily.py [--date YYYYMMDD] [--dry-run] [--skip-search]
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TMP_DIR = Path(".tmp")
TMP_DIR.mkdir(exist_ok=True)

DAILY_CAP = 10
SCORE_THRESHOLD = 85
PYTHON = sys.executable


def log_error(msg: str, date_str: str):
    path = TMP_DIR / f"errors_{date_str}.log"
    with open(path, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    print(f"ERROR: {msg}")


def run_tool(args: list[str]) -> int:
    result = subprocess.run([PYTHON] + args)
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--dry-run", action="store_true", help="Fill forms but do not submit")
    parser.add_argument("--skip-search", action="store_true", help="Skip LinkedIn search, use existing jobs file")
    args = parser.parse_args()

    date_str = args.date
    print(f"\n{'='*60}")
    print(f"Daily Job Search — {date_str}")
    print(f"{'='*60}\n")

    # Step 1: Search LinkedIn
    jobs_path = TMP_DIR / f"jobs_{date_str}.json"
    if not args.skip_search or not jobs_path.exists():
        print("Step 1: Searching LinkedIn...")
        rc = run_tool(["tools/search_linkedin_jobs.py", "--date", date_str])
        if rc != 0:
            log_error("LinkedIn search failed — aborting daily run", date_str)
            return
    else:
        print(f"Step 1: Skipping search, using existing {jobs_path}")

    if not jobs_path.exists():
        log_error(f"Jobs file not found: {jobs_path}", date_str)
        return

    with open(jobs_path) as f:
        all_jobs = json.load(f)
    print(f"  Found {len(all_jobs)} jobs\n")

    # Step 2: Deduplicate
    print("Step 2: Deduplicating...")
    applied_index = Path("applied/index.json")
    applied_ids: set[str] = set()
    if applied_index.exists():
        with open(applied_index) as f:
            applied_ids = set(json.load(f).keys())

    new_jobs = [j for j in all_jobs if j.get("job_id") not in applied_ids]
    print(f"  {len(new_jobs)} new jobs after removing {len(all_jobs) - len(new_jobs)} already-processed\n")

    if not new_jobs:
        print("No new jobs to process today.")
        return

    # Step 3: Score jobs — write filtered jobs to a temp file, then call scorer
    print("Step 3: Scoring jobs...")
    rc = run_tool(["tools/score_job_match.py", "--jobs-file", str(jobs_path), "--date", date_str])
    if rc != 0:
        log_error("Scoring failed", date_str)
        return

    scored_path = TMP_DIR / f"scored_{date_str}.json"
    with open(scored_path) as f:
        scored_jobs = json.load(f)

    # Re-apply dedup (scorer processed all_jobs; filter out already-applied here)
    scored_new = [j for j in scored_jobs if j.get("job_id") not in applied_ids]
    matches = sorted(
        [j for j in scored_new if j.get("match_score", 0) >= SCORE_THRESHOLD],
        key=lambda x: x.get("match_score", 0),
        reverse=True,
    )
    print(f"  Matches (≥{SCORE_THRESHOLD}): {len(matches)}/{len(scored_new)}\n")

    # Step 4: Apply to matches
    apply_queue = matches[:DAILY_CAP]
    capped = matches[DAILY_CAP:]

    print(f"Step 4: Applying to {len(apply_queue)} jobs (cap={DAILY_CAP}, dry_run={args.dry_run})...")

    for job in apply_queue:
        job_id = job["job_id"]
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        score = job.get("match_score", 0)
        reason = job.get("match_reason", "")
        apply_type = job.get("apply_type", "external")
        apply_url = job.get("apply_url", "")

        print(f"\n  [{score}/100] {title} at {company}")

        # Tailor resume + cover letter
        rc = run_tool(["tools/tailor_resume.py", "--job-id", job_id, "--date", date_str])
        if rc != 0:
            log_error(f"Tailoring failed for {job_id}", date_str)
            run_tool(["tools/log_application.py",
                      "--job-id", job_id, "--title", title, "--company", company,
                      "--status", "failed", "--notes", "Tailoring step failed"])
            continue

        # Generate PDF
        rc = run_tool(["tools/generate_pdf.py",
                       "--job-id", job_id, "--company", company,
                       "--title", title, "--date", date_str])
        if rc != 0:
            log_error(f"PDF generation failed for {job_id}", date_str)
            run_tool(["tools/log_application.py",
                      "--job-id", job_id, "--title", title, "--company", company,
                      "--status", "failed", "--notes", "PDF generation failed"])
            continue

        # Determine PDF path (mirrors sanitize_filename logic in generate_pdf.py)
        import re as _re
        def _slug(t): return _re.sub(r"[^\w\s-]", "", t).strip().replace(" ", "_")[:40]
        company_slug = _slug(company)
        title_slug = _slug(title)
        resume_pdf = str(Path("resume/versions") / f"resume_{company_slug}_{title_slug}_{date_str}.pdf")
        cover_letter_path = str(TMP_DIR / f"cover_{job_id}.md")

        # Submit application
        dry_flag = ["--dry-run"] if args.dry_run else []
        if apply_type == "easy_apply":
            apply_result_raw = subprocess.run(
                [PYTHON, "tools/apply_linkedin_easy.py",
                 "--job-id", job_id,
                 "--resume-pdf", resume_pdf,
                 "--cover-letter-file", cover_letter_path] + dry_flag,
                capture_output=True, text=True,
            )
        else:
            apply_result_raw = subprocess.run(
                [PYTHON, "tools/apply_external.py",
                 "--url", apply_url,
                 "--resume-pdf", resume_pdf,
                 "--cover-letter-file", cover_letter_path,
                 "--job-id", job_id] + dry_flag,
                capture_output=True, text=True,
            )

        # Parse JSON result from stdout
        status = "failed"
        notes = ""
        try:
            result = json.loads(apply_result_raw.stdout.strip().split("\n")[-1])
            status = result.get("status", "failed")
            notes = result.get("notes", "")
        except Exception:
            notes = apply_result_raw.stdout[:200] or apply_result_raw.stderr[:200]

        print(f"    Status: {status} — {notes}")

        run_tool(["tools/log_application.py",
                  "--job-id", job_id,
                  "--title", title,
                  "--company", company,
                  "--location", job.get("location", ""),
                  "--jd-url", apply_url,
                  "--score", str(score),
                  "--reason", reason,
                  "--resume-pdf", resume_pdf,
                  "--cover-letter", cover_letter_path,
                  "--status", status,
                  "--notes", notes])

    # Log capped jobs
    for job in capped:
        run_tool(["tools/log_application.py",
                  "--job-id", job["job_id"],
                  "--title", job.get("title", ""),
                  "--company", job.get("company", ""),
                  "--location", job.get("location", ""),
                  "--jd-url", job.get("apply_url", ""),
                  "--score", str(job.get("match_score", 0)),
                  "--reason", job.get("match_reason", ""),
                  "--status", "capped_skipped",
                  "--notes", f"Daily cap of {DAILY_CAP} reached"])

    print(f"\n{'='*60}")
    print(f"Done. Applied: {len(apply_queue)}, Capped: {len(capped)}, Non-matches: {len(scored_new) - len(matches)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
