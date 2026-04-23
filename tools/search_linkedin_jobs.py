"""
Search LinkedIn for jobs posted in the last 24 hours.
Outputs: .tmp/jobs_YYYYMMDD.json
Usage: python tools/search_linkedin_jobs.py [--login-only] [--date YYYYMMDD]
"""
import argparse
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

SESSION_DIR = Path(".tmp/linkedin_session")
TMP_DIR = Path(".tmp")
TMP_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

SEARCH_QUERIES = [
    "Senior Data Engineer",
    "Data Architect",
    "Principal Engineer Data Platform",
    "Engineering Manager Data",
    "Distributed Systems Engineer",
    "Staff Engineer Data",
]

LOCATIONS = ["Dallas, TX", "Remote"]


def log_error(msg: str, date_str: str):
    path = TMP_DIR / f"errors_{date_str}.log"
    with open(path, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    print(f"ERROR: {msg}")


def human_delay():
    time.sleep(random.uniform(1.0, 3.0))


def login(page, email: str, password: str) -> bool:
    print("Logging in to LinkedIn...")
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    human_delay()

    try:
        page.fill("#username", email, timeout=10000)
        page.fill("#password", password, timeout=10000)
        page.click('[type="submit"]', timeout=10000)
    except PlaywrightTimeout:
        print(f"Could not fill login form. Current URL: {page.url}")
        return False

    # Wait up to 90 seconds — gives time to complete 2FA or security challenge manually
    print("Waiting for LinkedIn to load (up to 90s — complete any verification in the browser)...")
    try:
        page.wait_for_url("**/feed**", timeout=90000)
        print("Login successful.")
        return True
    except PlaywrightTimeout:
        if "checkpoint" in page.url or "challenge" in page.url or "login" in page.url:
            print(f"Login did not complete. Still on: {page.url}")
            print("If a verification window appeared, complete it and re-run this script.")
        else:
            print(f"Unexpected URL after login: {page.url}")
        return False


def is_logged_in(page) -> bool:
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    human_delay()
    return "/feed" in page.url and "login" not in page.url


def extract_job_id(url: str) -> str:
    match = re.search(r"/jobs/view/(\d+)", url)
    return match.group(1) if match else ""


def get_jd_text(page) -> str:
    try:
        desc = page.locator(".job-details-jobs-unified-top-card__job-insight, .jobs-description__content, .jobs-box__html-content")
        return desc.first.inner_text(timeout=5000)
    except Exception:
        try:
            return page.locator('[class*="description"]').first.inner_text(timeout=3000)
        except Exception:
            return ""


def get_apply_type_and_url(page) -> tuple[str, str]:
    try:
        easy_apply = page.locator('.jobs-apply-button--top-card button:has-text("Easy Apply"), .jobs-apply-button button:has-text("Easy Apply")')
        if easy_apply.count() > 0:
            return "easy_apply", page.url
        external = page.locator('.jobs-apply-button--top-card a[href], .jobs-apply-button a[href]')
        if external.count() > 0:
            href = external.first.get_attribute("href") or ""
            return "external", href
    except Exception:
        pass
    return "external", page.url


def search_jobs(page, query: str, location: str, date_str: str) -> list[dict]:
    jobs = []
    encoded_query = query.replace(" ", "%20")
    encoded_location = location.replace(" ", "%20").replace(",", "%2C")
    # f_TPR=r86400 = last 24 hours; f_E=4,5 = Mid-Senior, Director
    url = (
        f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}"
        f"&location={encoded_location}&f_TPR=r86400&f_E=4%2C5&sortBy=DD"
    )
    print(f"Searching: {query} in {location}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay()
    except PlaywrightTimeout:
        log_error(f"Timeout loading search results for '{query}' in '{location}'", date_str)
        return jobs

    # Check for security challenge after navigation
    if "checkpoint" in page.url or "challenge" in page.url:
        log_error("LinkedIn security challenge during search — aborting", date_str)
        raise RuntimeError("LinkedIn security challenge")

    # Collect job card links
    try:
        page.wait_for_selector(".jobs-search-results__list-item, .job-card-container", timeout=10000)
    except PlaywrightTimeout:
        print(f"  No results found for '{query}' in '{location}'")
        return jobs

    job_cards = page.locator(".job-card-container__link, .base-card__full-link")
    job_urls = []
    for i in range(min(job_cards.count(), 15)):
        href = job_cards.nth(i).get_attribute("href") or ""
        if href and "/jobs/view/" in href:
            job_urls.append(href.split("?")[0])

    job_urls = list(dict.fromkeys(job_urls))  # deduplicate preserving order

    for job_url in job_urls:
        job_id = extract_job_id(job_url)
        if not job_id:
            continue
        human_delay()
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
        except PlaywrightTimeout:
            continue

        title = ""
        company = ""
        job_location = ""
        posted = ""

        try:
            title = page.locator(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title").first.inner_text(timeout=4000).strip()
        except Exception:
            pass
        try:
            company = page.locator(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name").first.inner_text(timeout=4000).strip()
        except Exception:
            pass
        try:
            job_location = page.locator(".job-details-jobs-unified-top-card__primary-description-without-tagline, .jobs-unified-top-card__bullet").first.inner_text(timeout=4000).strip()
        except Exception:
            pass
        try:
            posted = page.locator(".job-details-jobs-unified-top-card__posted-date, .jobs-unified-top-card__posted-date").first.inner_text(timeout=4000).strip()
        except Exception:
            pass

        jd_text = get_jd_text(page)
        apply_type, apply_url = get_apply_type_and_url(page)

        if not title or not jd_text:
            continue

        jobs.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": job_location or location,
            "apply_type": apply_type,
            "apply_url": apply_url or job_url,
            "jd_text": jd_text,
            "posted_date": posted,
            "search_query": query,
        })
        print(f"  Found: {title} at {company}")

    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login-only", action="store_true", help="Just log in and save session, then exit")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="Date string YYYYMMDD")
    args = parser.parse_args()

    email = os.environ.get("LINKEDIN_EMAIL", "")
    password = os.environ.get("LINKEDIN_PASSWORD", "")
    if not email or not password:
        print("ERROR: LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in .env")
        raise SystemExit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,  # visible window for first login; switch to True once session is saved
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = browser.new_page()

        if not is_logged_in(page):
            ok = login(page, email, password)
            if not ok:
                log_error("Login failed", args.date)
                browser.close()
                raise SystemExit(1)

        if args.login_only:
            print("Login-only mode: session saved.")
            browser.close()
            return

        all_jobs: list[dict] = []
        seen_ids: set[str] = set()

        try:
            for query in SEARCH_QUERIES:
                for location in LOCATIONS:
                    new_jobs = search_jobs(page, query, location, args.date)
                    for job in new_jobs:
                        if job["job_id"] not in seen_ids:
                            seen_ids.add(job["job_id"])
                            all_jobs.append(job)
                    human_delay()
        except RuntimeError as e:
            log_error(str(e), args.date)
            browser.close()
            raise SystemExit(1)

        browser.close()

    out_path = TMP_DIR / f"jobs_{args.date}.json"
    with open(out_path, "w") as f:
        json.dump(all_jobs, f, indent=2)
    print(f"\nFound {len(all_jobs)} unique jobs. Saved to {out_path}")


if __name__ == "__main__":
    main()
