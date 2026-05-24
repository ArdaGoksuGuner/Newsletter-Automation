# Newsletter Workflow

## Objective
Given a topic from the user, produce a fully written, designed, and sent HTML newsletter — including research, writing, data charts, and delivery via Gmail.

## Required Inputs
- `topic` — the newsletter subject (required; ask if not given)
- `focus_areas` — comma-separated aspects to emphasize (optional; ask if not given)
- `tone` — writing style (optional; default: "analytical but accessible")
- `target_length` — short / medium / long (optional; default: medium)
- `subject_index` — which of the 3 subject lines to use: 0, 1, or 2 (ask the user at Step 3)
- `dry_run` — true/false (default: true; require explicit confirmation before setting false)

---

## Prerequisites Check

Before starting, verify these keys exist in `.env`:
```
ANTHROPIC_API_KEY
TAVILY_API_KEY
GMAIL_ADDRESS
GMAIL_APP_PASSWORD
NEWSLETTER_FROM_NAME
GOOGLE_SHEETS_SUBSCRIBERS_ID
CLOUDINARY_CLOUD_NAME
CLOUDINARY_API_KEY
CLOUDINARY_API_SECRET
```

If any are missing, stop and tell the user which ones to add. Do not proceed until they are present.

Also verify `credentials.json` exists in the project root (Google Sheets OAuth). If missing, tell the user to download it from the Google Cloud Console.

---

## Step 0 — Check Topic History

Read `.tmp/newsletter_log.json` if it exists. Scan past topics and subjects. If the same (or very similar) topic was covered in the last 6 months, tell the user:

> "I noticed we covered [previous topic] on [date]. Would you like to approach this from a different angle, or proceed anyway?"

Wait for their response before continuing.

---

## Step 1 — Research

Run:
```
python tools/research.py --topic "{topic}" --focus "{focus_areas}" --depth basic
```

The tool prints the output file path to stdout. Save it as `research_path`.

**Quality check:** Read the output JSON and verify:
- At least 3 `key_findings` with real specifics
- At least 1 entry in `chart_data`

If findings are fewer than 3, re-run with a broader or rephrased topic. If still thin after 2 attempts, tell the user the topic may have limited current coverage and ask if they want to proceed or pick a different angle.

If `chart_data` is empty, note this — Step 4 will be skipped. Not every topic has chartable data.

---

## Step 2 — Write Content

Run:
```
python tools/write_newsletter.py \
  --research {research_path} \
  --tone "{tone}" \
  --target-length {target_length}
```

Save the output file path as `content_path`.

**Quality check:** Verify the output JSON has:
- Exactly 3 `subject_lines`
- A `preheader_text` ≤100 characters
- At least 2 `sections`
- A `plain_text_version` (non-empty)

If any are missing, do not proceed — re-run or fix the output manually.

---

## Step 3 — Present Subject Lines to User

Read `subject_lines` from the content JSON. Present all 3 clearly:

> Here are 3 subject line options for this newsletter:
>
> **0.** [subject_line_0]
> **1.** [subject_line_1]
> **2.** [subject_line_2]
>
> Which would you like to use? (Reply with 0, 1, or 2)

**Wait for the user's choice before continuing.**

Save the chosen index as `subject_index`.

---

## Step 4 — Generate Charts

If `chart_data` in the research JSON is non-empty, run:
```
python tools/generate_charts.py \
  --research {research_path} \
  --style light
```

The tool prints a JSON dict to stdout: `{"chart_name": "/abs/path/to/chart.png"}`.
Save this as `charts_json`. If the output is `{}`, skip Step 5.

If `chart_data` was empty, set `charts_json = "{}"` and skip Step 5.

---

## Step 5 — Upload Charts to Cloudinary

If `charts_json` is not `{}`, run:
```
python tools/upload_images.py \
  --charts '{charts_json}' \
  --folder "newsletters" \
  --topic-slug "{topic_slug}"
```

The tool prints a JSON dict to stdout: `{"chart_name": "https://res.cloudinary.com/..."}`.
Save this as `image_urls_json`.

If a chart fails to upload, note it and continue — the template handles missing images gracefully.

If `charts_json` is `{}`, set `image_urls_json = "{}"`.

---

## Step 6 — Build HTML

Run:
```
python tools/build_html.py \
  --content {content_path} \
  --images '{image_urls_json}' \
  --subject-index {subject_index}
```

The tool prints a JSON object to stdout containing `html_path` and `subject`.
Save both values.

---

## Step 7 — User Review

Tell the user:

> The newsletter HTML is ready.
>
> **File:** `{html_path}`
> **Subject:** {subject}
> **Preheader:** {preheader_text}
>
> Open the file in a browser to preview it. When you're happy with it, reply **"approved"** and I'll send a test email to your own inbox first.

**Wait for "approved" (or feedback).** If they have feedback, make the adjustments they request by editing the content JSON or HTML directly, then re-run `build_html.py`.

---

## Step 8 — Dry-Run Send

Once approved, run:
```
python tools/send_newsletter.py \
  --html {html_path} \
  --subject "{subject}" \
  --content {content_path} \
  --dry-run true
```

Tell the user:

> Test email sent to {GMAIL_ADDRESS}. Check your inbox — look at the subject line preview, preheader text, images, and mobile layout.
>
> When you're ready to send to the full list, reply **"send it"**.

**Wait for explicit "send it" confirmation before proceeding.**

---

## Step 9 — Full Send

Only after explicit "send it" confirmation, run:
```
python tools/send_newsletter.py \
  --html {html_path} \
  --subject "{subject}" \
  --content {content_path} \
  --dry-run false
```

Report results to the user:

> Newsletter sent. Results:
> - Recipients attempted: {recipients_attempted}
> - Successfully sent: {sent}
> - Failed: {failed}
>
> {If failed > 0: "Failed addresses logged to {errors_file}."}

---

## Step 10 — Log Confirmation

`send_newsletter.py` automatically appends to `.tmp/newsletter_log.json`. Confirm the log was updated by checking the file exists and the new entry is present.

The workflow is complete.

---

## Error Recovery

### Research returns thin results
Re-run `research.py` with a broader topic phrasing or add `--focus "include specific statistics, market size, growth rates, key companies"`. If still thin after 2 attempts, suggest alternative topic angles to the user.

### Chart generation returns `{}`
Check whether `chart_data` in the research JSON has entries. If not, the research prompt needs quantitative data. Re-run research with the focus explicitly requesting statistics: `--focus "market data, adoption rates, growth figures, comparative statistics"`.

### Cloudinary upload fails
1. Check all three Cloudinary keys are in `.env` (CLOUD_NAME, API_KEY, API_SECRET)
2. Try logging into the Cloudinary dashboard to confirm the account is active
3. The free tier has 25GB storage — if exceeded, delete old uploads from the dashboard
4. If upload still fails, continue without images — set `image_urls_json = "{}"` and note the newsletter will render without charts

### Gmail send fails
Common causes:
- `GMAIL_APP_PASSWORD` is wrong — must be the App Password (16-char code), not the Gmail login password
- 2FA is not enabled on the Google account — App Passwords require 2FA to be active
- Daily send limit reached (500/day for standard Gmail)

### HTML renders incorrectly in email client
- **Outlook**: Ensure the template uses only table-based layout (no Flexbox, Grid, position:absolute). Run premailer again.
- **Gmail clips**: Gmail clips emails over ~102KB. Run `wc -c {html_path}` to check size. Reduce content or remove large inline data.
- **Images not showing**: Check the Cloudinary URLs are accessible in a browser. Images must be HTTPS.

---

## Known Constraints
- Perplexity Sonar Pro: treat as 10 req/min to be safe
- Gmail SMTP: 500 emails/day (standard Gmail), 2,000/day (Google Workspace)
- Cloudinary free tier: 25GB storage, 25GB/month bandwidth
- Gmail clips emails over ~102KB total HTML size
- Always dry-run before full send — there is no unsend
- Never run `--dry-run false` without explicit "send it" from the user
