# Workflow: Job Application Submission

## Objective
Submit a job application using browser automation. Handle two paths: LinkedIn Easy Apply (native form) and external company sites.

## Path A: LinkedIn Easy Apply

### Steps
1. Navigate to `https://www.linkedin.com/jobs/view/{job_id}`
2. Click the "Easy Apply" button
3. Step through the modal form:
   - **Contact info**: Pre-fill from profile (name: Mano Wilson, email: xwilson@gmail.com, phone: 310-384-0402)
   - **Resume**: Upload the generated PDF from `resume/versions/`
   - **Cover letter field** (if present): Paste cover letter text
   - **Additional questions**: Answer yes/no questions using commonsense (years of experience, work authorization = US citizen, willing to relocate = no unless remote)
   - **Multi-step navigation**: Click "Next" or "Continue" until "Submit" button is available
4. Click "Submit"
5. Confirm success by checking for the "Application submitted" confirmation banner

### Failure Handling
- If the modal shows unexpected fields or a long multi-step questionnaire (>5 steps): abort, return `status = "manual_required"`
- If any step fails after 2 retries: return `status = "failed"` with the error
- Never click submit if any required field was left empty

### Dry-Run Mode
When `--dry-run` flag is set: navigate and fill the form but stop before clicking Submit. Take a screenshot to `.tmp/dryrun_{job_id}.png` and return `status = "dry_run_complete"`.

---

## Path B: External Site

### Steps
1. Navigate to the `apply_url` provided
2. Detect standard application form fields:
   - Name fields (first, last, or full name)
   - Email field
   - Phone field
   - Resume upload button (accept `.pdf`)
   - Cover letter textarea (if present)
3. Fill detected fields; skip fields that are ambiguous or require decisions
4. Do NOT click Submit if:
   - A CAPTCHA appears
   - The form has more than 8 required fields (too complex to automate reliably)
   - The page requires creating an account with a new password
   - The apply flow requires selecting from unknown dropdown values
5. If conditions above are met: return `status = "manual_required"` with the URL

### Failure Handling
- Network error or page fails to load: `status = "failed"`
- Unexpected redirect mid-form: abort, return `status = "manual_required"`

---

## Output Format
```json
{
  "status": "applied | manual_required | failed | dry_run_complete",
  "notes": "brief description of what happened",
  "screenshot": ".tmp/screenshot_{job_id}.png (if captured)"
}
```

## Important
Always call `tools/log_application.py` after this step regardless of status. Every attempt — successful or not — gets logged.
