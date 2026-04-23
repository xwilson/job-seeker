"""
Log a job application result to applied/YYYYMMDD_Company_Role.md
and update applied/index.json.

Usage:
  python tools/log_application.py --job-id 123 --title "Senior DE" --company "Acme"
    --location "Remote" --jd-url "https://..." --score 82
    --reason "Strong tech match" --resume-pdf "resume/versions/..."
    --cover-letter ".tmp/cover_123.md" --status applied --notes ""
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

APPLIED_DIR = Path("applied")
INDEX_PATH = APPLIED_DIR / "index.json"


def sanitize(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")[:40]


def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {}
    with open(INDEX_PATH) as f:
        return json.load(f)


def save_index(data: dict):
    with open(INDEX_PATH, "w") as f:
        json.dump(data, f, indent=2)


def log_application(
    job_id: str,
    title: str,
    company: str,
    location: str,
    jd_url: str,
    score: int,
    reason: str,
    resume_pdf: str,
    cover_letter: str,
    status: str,
    notes: str,
):
    APPLIED_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{date_str}_{sanitize(company)}_{sanitize(title)}.md"
    note_path = APPLIED_DIR / filename

    content = f"""# {title} at {company}

- **Date**: {datetime.now().strftime("%Y-%m-%d")}
- **Location**: {location}
- **JD URL**: {jd_url}
- **Match Score**: {score}/100
- **Match Reason**: {reason}
- **Resume**: {resume_pdf}
- **Cover Letter**: {cover_letter}
- **Status**: {status}
- **Notes**: {notes or "—"}
"""
    with open(note_path, "w") as f:
        f.write(content)

    index = load_index()
    index[job_id] = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": status,
        "company": company,
        "title": title,
        "note_file": filename,
    }
    save_index(index)
    print(f"Logged: {filename} (status={status})")
    return str(note_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--location", default="")
    parser.add_argument("--jd-url", default="")
    parser.add_argument("--score", type=int, default=0)
    parser.add_argument("--reason", default="")
    parser.add_argument("--resume-pdf", default="")
    parser.add_argument("--cover-letter", default="")
    parser.add_argument("--status", default="applied",
                        choices=["applied", "manual_required", "failed", "capped_skipped"])
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    log_application(
        job_id=args.job_id,
        title=args.title,
        company=args.company,
        location=args.location,
        jd_url=args.jd_url,
        score=args.score,
        reason=args.reason,
        resume_pdf=args.resume_pdf,
        cover_letter=args.cover_letter,
        status=args.status,
        notes=args.notes,
    )


if __name__ == "__main__":
    main()
