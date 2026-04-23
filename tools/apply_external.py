"""
Attempt to apply to a job on an external company website via Playwright.
Fills standard form fields; returns manual_required for complex forms.

Usage:
  python tools/apply_external.py --url "https://..." --resume-pdf resume/versions/out.pdf [--dry-run]
"""
import argparse
import json
import random
import time
from pathlib import Path

import os

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

TMP_DIR = Path(".tmp")

_first = os.environ.get("APPLICANT_FIRST_NAME", "")
_last = os.environ.get("APPLICANT_LAST_NAME", "")
CONTACT = {
    "first_name": _first,
    "last_name": _last,
    "full_name": f"{_first} {_last}".strip(),
    "email": os.environ.get("APPLICANT_EMAIL", ""),
    "phone": os.environ.get("APPLICANT_PHONE", ""),
}

# Selectors to try for each field type
FIELD_PATTERNS = {
    "first_name": ['input[name*="first"][type="text"]', 'input[id*="firstName"]', 'input[placeholder*="First"]'],
    "last_name": ['input[name*="last"][type="text"]', 'input[id*="lastName"]', 'input[placeholder*="Last"]'],
    "full_name": ['input[name*="name"][type="text"]', 'input[id*="fullName"]', 'input[placeholder*="Full name"]', 'input[placeholder*="Your name"]'],
    "email": ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]'],
    "phone": ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]'],
}

MAX_REQUIRED_FIELDS = 8  # abort if form looks too complex


def human_delay():
    time.sleep(random.uniform(0.5, 1.5))


def try_fill(page, patterns: list[str], value: str) -> bool:
    for selector in patterns:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=1500):
                existing = el.input_value(timeout=1000)
                if not existing:
                    el.fill(value, timeout=3000)
                return True
        except Exception:
            continue
    return False


def count_required_fields(page) -> int:
    try:
        required = page.locator('[required], [aria-required="true"]')
        return required.count()
    except Exception:
        return 0


def has_captcha(page) -> bool:
    try:
        return (
            page.locator('iframe[src*="recaptcha"], iframe[src*="captcha"], .g-recaptcha, [class*="captcha"]').count() > 0
        )
    except Exception:
        return False


def requires_account_creation(page) -> bool:
    try:
        content = page.content().lower()
        return "create an account" in content or "sign up to apply" in content or "register to apply" in content
    except Exception:
        return False


def apply_external(url: str, resume_pdf: str, cover_letter_text: str = "", dry_run: bool = False, job_id: str = "unknown") -> dict:
    TMP_DIR.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            human_delay()

            # Abort conditions
            if has_captcha(page):
                browser.close()
                return {"status": "manual_required", "notes": "CAPTCHA detected", "url": url}

            if requires_account_creation(page):
                browser.close()
                return {"status": "manual_required", "notes": "Account creation required", "url": url}

            required_count = count_required_fields(page)
            if required_count > MAX_REQUIRED_FIELDS:
                browser.close()
                return {"status": "manual_required", "notes": f"Form has {required_count} required fields — too complex", "url": url}

            # Fill contact fields
            try_fill(page, FIELD_PATTERNS["first_name"], CONTACT["first_name"])
            try_fill(page, FIELD_PATTERNS["last_name"], CONTACT["last_name"])
            try_fill(page, FIELD_PATTERNS["full_name"], CONTACT["full_name"])
            try_fill(page, FIELD_PATTERNS["email"], CONTACT["email"])
            try_fill(page, FIELD_PATTERNS["phone"], CONTACT["phone"])
            human_delay()

            # Resume upload
            resume_uploaded = False
            try:
                upload = page.locator('input[type="file"][accept*="pdf"], input[type="file"]').first
                if upload.is_visible(timeout=2000):
                    upload.set_input_files(resume_pdf, timeout=8000)
                    resume_uploaded = True
                    human_delay()
            except Exception:
                pass

            # Cover letter textarea
            if cover_letter_text:
                try:
                    cl_area = page.locator('textarea[name*="cover"], textarea[id*="cover"], textarea[placeholder*="cover"]').first
                    if cl_area.is_visible(timeout=2000):
                        cl_area.fill(cover_letter_text[:3000], timeout=3000)
                        human_delay()
                except Exception:
                    pass

            if dry_run:
                screenshot_path = str(TMP_DIR / f"dryrun_ext_{job_id}.png")
                page.screenshot(path=screenshot_path)
                browser.close()
                return {"status": "dry_run_complete", "notes": f"Form filled (resume_uploaded={resume_uploaded}), screenshot: {screenshot_path}", "url": url}

            # Find and click submit
            submit_btn = page.locator(
                'button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Apply Now"), button:has-text("Send Application")'
            ).first
            if submit_btn.is_visible(timeout=3000):
                submit_btn.click()
                human_delay(1, 2)
                browser.close()
                return {"status": "applied", "notes": f"Submit clicked (resume_uploaded={resume_uploaded})", "url": url}
            else:
                browser.close()
                return {"status": "manual_required", "notes": "Could not locate submit button", "url": url}

        except PlaywrightTimeout as e:
            try:
                browser.close()
            except Exception:
                pass
            return {"status": "failed", "notes": f"Timeout: {e}", "url": url}
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            return {"status": "failed", "notes": str(e), "url": url}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--resume-pdf", required=True)
    parser.add_argument("--cover-letter-file", default="")
    parser.add_argument("--job-id", default="unknown")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cover_text = ""
    if args.cover_letter_file:
        p = Path(args.cover_letter_file)
        if p.exists():
            cover_text = p.read_text(encoding="utf-8")

    result = apply_external(
        url=args.url,
        resume_pdf=args.resume_pdf,
        cover_letter_text=cover_text,
        dry_run=args.dry_run,
        job_id=args.job_id,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
