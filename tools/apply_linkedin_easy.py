"""
Submit a LinkedIn Easy Apply application via Playwright.

Usage:
  python tools/apply_linkedin_easy.py --job-id 1234567 --resume-pdf resume/versions/resume_Acme_SDE_20260422.pdf [--dry-run]
"""
import argparse
import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

SESSION_DIR = Path(".tmp/linkedin_session")
TMP_DIR = Path(".tmp")

CONTACT = {
    "first_name": os.environ.get("APPLICANT_FIRST_NAME", ""),
    "last_name": os.environ.get("APPLICANT_LAST_NAME", ""),
    "email": os.environ.get("APPLICANT_EMAIL", ""),
    "phone": os.environ.get("APPLICANT_PHONE", ""),
}


def human_delay(low=0.5, high=1.5):
    time.sleep(random.uniform(low, high))


def fill_text_if_empty(page, selector: str, value: str):
    try:
        el = page.locator(selector).first
        existing = el.input_value(timeout=2000)
        if not existing:
            el.fill(value, timeout=3000)
    except Exception:
        pass


def handle_contact_step(page):
    fill_text_if_empty(page, 'input[id*="firstName"], input[name*="firstName"]', CONTACT["first_name"])
    fill_text_if_empty(page, 'input[id*="lastName"], input[name*="lastName"]', CONTACT["last_name"])
    fill_text_if_empty(page, 'input[id*="email"], input[type="email"]', CONTACT["email"])
    fill_text_if_empty(page, 'input[id*="phone"], input[type="tel"]', CONTACT["phone"])
    human_delay()


def handle_resume_step(page, resume_pdf: str):
    try:
        upload_input = page.locator('input[type="file"]').first
        upload_input.set_input_files(resume_pdf, timeout=8000)
        human_delay()
    except Exception:
        pass  # Resume upload field may not be present on every step


def handle_cover_letter_step(page, cover_letter_text: str):
    try:
        textarea = page.locator('textarea[id*="cover"], textarea[placeholder*="cover"]').first
        if textarea.is_visible(timeout=2000):
            textarea.fill(cover_letter_text[:3000], timeout=3000)
            human_delay()
    except Exception:
        pass


def count_steps(page) -> int:
    try:
        progress = page.locator('.artdeco-completeness-meter-linear__bar, [aria-label*="step"]').first
        text = progress.inner_text(timeout=2000)
        parts = text.split("/")
        if len(parts) == 2:
            return int(parts[1].strip())
    except Exception:
        pass
    return 0


def apply_easy(job_id: str, resume_pdf: str, cover_letter_text: str = "", dry_run: bool = False) -> dict:
    TMP_DIR.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = browser.new_page()

        try:
            job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
            page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
            human_delay()

            # Click Easy Apply button
            easy_btn = page.locator('button:has-text("Easy Apply")').first
            if not easy_btn.is_visible(timeout=5000):
                browser.close()
                return {"status": "failed", "notes": "Easy Apply button not found on page"}
            easy_btn.click()
            human_delay(1, 2)

            # Safety check: abort if too many steps (>5)
            total_steps = count_steps(page)
            if total_steps > 5:
                browser.close()
                return {"status": "manual_required", "notes": f"Form has {total_steps} steps — too complex for automation"}

            step_count = 0
            max_steps = 8  # hard cap to prevent infinite loops

            while step_count < max_steps:
                step_count += 1
                human_delay()

                handle_contact_step(page)
                handle_resume_step(page, resume_pdf)
                handle_cover_letter_step(page, cover_letter_text)

                # Check for submit button
                submit_btn = page.locator('button:has-text("Submit application"), button:has-text("Submit")').first
                if submit_btn.is_visible(timeout=2000):
                    if dry_run:
                        screenshot_path = str(TMP_DIR / f"dryrun_{job_id}.png")
                        page.screenshot(path=screenshot_path)
                        browser.close()
                        return {"status": "dry_run_complete", "notes": f"Form ready, screenshot: {screenshot_path}"}
                    submit_btn.click()
                    human_delay(1, 2)
                    # Confirm submission
                    try:
                        page.wait_for_selector('[aria-label*="submitted"], h2:has-text("Application submitted")', timeout=8000)
                        browser.close()
                        return {"status": "applied", "notes": "Application submitted successfully"}
                    except PlaywrightTimeout:
                        browser.close()
                        return {"status": "applied", "notes": "Submit clicked; could not confirm banner"}

                # Try next/continue button
                next_btn = page.locator('button:has-text("Next"), button:has-text("Continue"), button:has-text("Review")').first
                if next_btn.is_visible(timeout=2000):
                    next_btn.click()
                    human_delay()
                    continue

                # No navigation button found — unexpected state
                browser.close()
                return {"status": "manual_required", "notes": "Could not advance form — unexpected state"}

            browser.close()
            return {"status": "manual_required", "notes": f"Exceeded {max_steps} step limit"}

        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            return {"status": "failed", "notes": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--resume-pdf", required=True)
    parser.add_argument("--cover-letter-file", default="", help="Path to cover letter .md file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cover_text = ""
    if args.cover_letter_file:
        p = Path(args.cover_letter_file)
        if p.exists():
            cover_text = p.read_text(encoding="utf-8")

    result = apply_easy(
        job_id=args.job_id,
        resume_pdf=args.resume_pdf,
        cover_letter_text=cover_text,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
