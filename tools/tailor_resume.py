"""
Generate a tailored resume and cover letter for a specific job using OpenRouter.
Outputs:
  .tmp/resume_tailored_{job_id}.md
  .tmp/cover_{job_id}.md

Usage:
  python tools/tailor_resume.py --job-id 1234567 --date 20260422
  python tools/tailor_resume.py --job-file path/to/job.json
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


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set in .env")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def load_profile() -> str:
    return PROFILE_PATH.read_text(encoding="utf-8")


def call_llm(client: OpenAI, system: str, user: str) -> str:
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=3000,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt == 0:
                print(f"  LLM error, retrying in 10s: {e}")
                time.sleep(10)
            else:
                raise


def generate_tailored_resume(client: OpenAI, profile: str, job: dict) -> str:
    system = f"""You are a resume tailoring assistant. Customize the candidate's resume to best match a specific job description WITHOUT adding any experience, skills, or accomplishments not already in the master profile.

Rules:
- Reorder experience bullets to put the most JD-relevant ones first
- Adjust the professional summary to echo the JD's language and priorities
- Do NOT add, fabricate, or embellish any content — only restructure and reword what exists
- Keep total length similar to the original (aim for 1-2 pages when rendered)
- Output clean markdown suitable for PDF conversion

Master Profile:
{profile}"""

    user = f"""Job Title: {job.get("title", "")}
Company: {job.get("company", "")}
Location: {job.get("location", "")}

Job Description:
{job.get("jd_text", "")[:5000]}

Produce the tailored resume in markdown format."""

    return call_llm(client, system, user)


def generate_cover_letter(client: OpenAI, profile: str, job: dict) -> str:
    system = f"""You are writing a professional cover letter. Keep it concise: exactly 3 paragraphs.

Paragraph 1 (Hook): Why this specific role at this specific company excites the candidate. Reference something concrete from the JD.
Paragraph 2 (Fit): Highlight 2-3 specific accomplishments from the master profile that directly match the JD requirements. Be specific with technologies, scale, or outcomes.
Paragraph 3 (Close): Express enthusiasm, note availability, and invite a conversation.

Tone: Professional but not stiff. Confident, not boastful. First person.

Sign off with:
{os.environ.get("APPLICANT_FIRST_NAME", "")} {os.environ.get("APPLICANT_LAST_NAME", "")}
{os.environ.get("APPLICANT_EMAIL", "")} | {os.environ.get("APPLICANT_PHONE", "")}

Master Profile:
{profile}"""

    user = f"""Job Title: {job.get("title", "")}
Company: {job.get("company", "")}
Location: {job.get("location", "")}

Job Description:
{job.get("jd_text", "")[:5000]}

Write the cover letter."""

    return call_llm(client, system, user)


def tailor(job: dict) -> tuple[Path, Path]:
    TMP_DIR.mkdir(exist_ok=True)
    job_id = job["job_id"]
    client = get_client()
    profile = load_profile()

    print(f"Tailoring resume for {job.get('title')} at {job.get('company')}...")
    resume_md = generate_tailored_resume(client, profile, job)
    resume_path = TMP_DIR / f"resume_tailored_{job_id}.md"
    resume_path.write_text(resume_md, encoding="utf-8")
    print(f"  Resume saved: {resume_path}")

    print("  Generating cover letter...")
    cover_md = generate_cover_letter(client, profile, job)
    cover_path = TMP_DIR / f"cover_{job_id}.md"
    cover_path.write_text(cover_md, encoding="utf-8")
    print(f"  Cover letter saved: {cover_path}")

    return resume_path, cover_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", help="Job ID to tailor for (loads from today's scored file)")
    parser.add_argument("--job-file", help="Path to a single job JSON file")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    from datetime import datetime
    date_str = args.date or datetime.now().strftime("%Y%m%d")

    if args.job_file:
        with open(args.job_file) as f:
            job = json.load(f)
    elif args.job_id:
        scored_path = TMP_DIR / f"scored_{date_str}.json"
        if not scored_path.exists():
            # Fall back to raw jobs file
            scored_path = TMP_DIR / f"jobs_{date_str}.json"
        with open(scored_path) as f:
            jobs = json.load(f)
        matching = [j for j in jobs if j.get("job_id") == args.job_id]
        if not matching:
            print(f"ERROR: job_id {args.job_id} not found")
            raise SystemExit(1)
        job = matching[0]
    else:
        print("ERROR: Provide --job-id or --job-file")
        raise SystemExit(1)

    resume_path, cover_path = tailor(job)
    print(f"\nDone.\n  Resume: {resume_path}\n  Cover letter: {cover_path}")


if __name__ == "__main__":
    main()
