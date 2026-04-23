"""
Convert a tailored resume markdown to a styled PDF using WeasyPrint.
Output: resume/versions/resume_{Company}_{Role}_{YYYYMMDD}.pdf

Usage:
  python tools/generate_pdf.py --job-id 1234567 --company "Acme" --title "Senior DE" --date 20260422
  python tools/generate_pdf.py --resume-md .tmp/resume_tailored_123.md --output resume/versions/out.pdf
"""
import argparse
import re
from datetime import datetime
from pathlib import Path

import markdown as md_lib

VERSIONS_DIR = Path("resume/versions")
TMP_DIR = Path(".tmp")

CSS = """
@page {
    margin: 0.75in 0.75in 0.75in 0.75in;
    size: letter;
}
body {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1a1a1a;
}
h1 {
    font-size: 18pt;
    font-weight: bold;
    text-align: center;
    margin-bottom: 2px;
    border-bottom: 1.5px solid #333;
    padding-bottom: 4px;
}
h2 {
    font-size: 11pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 0.5px solid #aaa;
    margin-top: 10px;
    margin-bottom: 4px;
}
h3 {
    font-size: 10.5pt;
    font-weight: bold;
    margin-top: 6px;
    margin-bottom: 2px;
}
p {
    margin: 2px 0 4px 0;
}
ul {
    margin: 2px 0;
    padding-left: 18px;
}
li {
    margin-bottom: 2px;
}
strong {
    font-weight: bold;
}
em {
    font-style: italic;
    color: #444;
}
"""


def sanitize_filename(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")[:40]


def md_to_pdf(md_text: str, output_path: Path):
    try:
        from weasyprint import HTML, CSS as WeasyCss
    except ImportError:
        raise RuntimeError("weasyprint not installed. Run: pip install weasyprint")

    html_body = md_lib.markdown(md_text, extensions=["tables", "fenced_code"])
    full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>{html_body}</body></html>"""

    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    HTML(string=full_html).write_pdf(
        str(output_path),
        stylesheets=[WeasyCss(string=CSS)],
    )
    print(f"PDF generated: {output_path}")


def generate(job_id: str, company: str, title: str, date_str: str = None) -> Path:
    date_str = date_str or datetime.now().strftime("%Y%m%d")
    resume_md_path = TMP_DIR / f"resume_tailored_{job_id}.md"
    if not resume_md_path.exists():
        raise FileNotFoundError(f"Tailored resume not found: {resume_md_path}")

    company_slug = sanitize_filename(company)
    title_slug = sanitize_filename(title)
    output_path = VERSIONS_DIR / f"resume_{company_slug}_{title_slug}_{date_str}.pdf"

    md_text = resume_md_path.read_text(encoding="utf-8")
    md_to_pdf(md_text, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", help="Job ID (loads .tmp/resume_tailored_{id}.md)")
    parser.add_argument("--company", default="Company")
    parser.add_argument("--title", default="Role")
    parser.add_argument("--date", default=None)
    parser.add_argument("--resume-md", help="Direct path to resume markdown file")
    parser.add_argument("--output", help="Direct output PDF path")
    args = parser.parse_args()

    if args.resume_md and args.output:
        md_text = Path(args.resume_md).read_text(encoding="utf-8")
        VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        md_to_pdf(md_text, Path(args.output))
    elif args.job_id:
        date_str = args.date or datetime.now().strftime("%Y%m%d")
        out = generate(args.job_id, args.company, args.title, date_str)
        print(f"PDF: {out}")
    else:
        print("ERROR: Provide --job-id or both --resume-md and --output")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
