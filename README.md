# Newsletter Automation

A fully automated newsletter pipeline built on the **WAT framework** (Workflows · Agents · Tools). Give it a topic — it researches, writes, designs, and sends a polished HTML email with data charts in minutes.

---

## How it works

```
You provide a topic
        │
        ▼
┌───────────────────┐
│   Tavily Search   │  Web research — 8 sources, AI summary
└────────┬──────────┘
         │  raw results
         ▼
┌───────────────────┐
│  Claude Sonnet    │  Structures findings → JSON research brief
└────────┬──────────┘
         │  key findings · statistics · chart data · sources
         ▼
┌───────────────────┐
│  Claude Sonnet    │  Writes headline · sections · 3 subject lines
└────────┬──────────┘       preheader · takeaways · plain-text copy
         │
         ├──────────────────────────────────┐
         ▼                                  ▼
┌───────────────────┐            ┌──────────────────────┐
│    matplotlib     │  PNG       │    Jinja2 + premailer │
│    + seaborn      │ ─────────► │    Email template     │
└───────────────────┘  charts   └──────────┬───────────┘
         │                                  │
         ▼                                  │  inlined CSS HTML
┌───────────────────┐                       │
│    Cloudinary     │  public URLs ─────────┘
└───────────────────┘
         │
         ▼
┌───────────────────┐
│   Gmail SMTP      │  dry-run → review → send to full list
└───────────────────┘
```

---

## Features

- **Fully researched** — Tavily searches the live web; Claude synthesizes findings into structured data
- **Professionally written** — three subject line options, preheader text, multi-section body, key takeaways, plain-text fallback
- **Data-driven visuals** — bar, line, horizontal bar, and pie charts auto-generated from researched statistics
- **Email-safe HTML** — table-based layout, CSS inlined via premailer, mobile responsive, dark mode, Outlook-compatible
- **Human checkpoints** — subject line selection, HTML preview, dry-run to self, explicit confirmation before full send
- **Topic memory** — append-only send log prevents covering the same topic twice

---

## Tech stack

| Layer | Tool | Purpose |
|---|---|---|
| Research | [Tavily](https://tavily.com) | Live web search — 1,000 searches/month free |
| Writing | [Anthropic Claude](https://anthropic.com) | Research structuring + newsletter copy |
| Charts | matplotlib · seaborn | PNG chart generation from researched data |
| Image hosting | [Cloudinary](https://cloudinary.com) | Public URLs for chart images in email |
| Email HTML | Jinja2 · premailer | Template rendering + CSS inlining |
| Delivery | Gmail SMTP | Sends via App Password — no custom domain needed |
| Subscribers | Google Sheets | Name · email · subscribed columns |

---

## Project structure

```
newsletter-automation/
├── tools/
│   ├── research.py          # Tavily search → Claude → research JSON
│   ├── write_newsletter.py  # Claude → content JSON (copy + subject lines)
│   ├── generate_charts.py   # matplotlib → PNGs in .tmp/charts/
│   ├── upload_images.py     # Cloudinary upload → public URLs
│   ├── build_html.py        # Jinja2 + premailer → .tmp/newsletter.html
│   └── send_newsletter.py   # Gmail SMTP send (dry-run by default)
├── templates/
│   └── newsletter.html      # Jinja2 base template
├── workflows/
│   └── newsletter.md        # Agent SOP — step-by-step orchestration guide
├── CLAUDE.md                # WAT framework instructions
└── .env.example             # Required environment variables (rename to .env)
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/ArdaGoksuGuner/newsletter-automation.git
cd newsletter-automation
pip install anthropic tavily-python matplotlib seaborn cloudinary \
            jinja2 premailer python-dotenv pillow gspread google-auth
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
# Anthropic — claude.ai/settings
ANTHROPIC_API_KEY=

# Tavily — app.tavily.com (free tier: 1,000 searches/month)
TAVILY_API_KEY=

# Gmail — Google Account → Security → 2-Step Verification → App Passwords
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Newsletter identity
NEWSLETTER_FROM_NAME=Your Newsletter Name
NEWSLETTER_SENDER_ADDRESS=City, Country

# Google Sheets subscriber list
# Column headers: name | email | subscribed (TRUE/FALSE)
GOOGLE_SHEETS_SUBSCRIBERS_ID=

# Cloudinary — cloudinary.com (free tier: 25 GB storage + bandwidth)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

### 3. Set up Google Sheets access

1. Create a [Google Cloud service account](https://console.cloud.google.com/) and download `credentials.json` to the project root
2. Share your subscriber Google Sheet with the service account email
3. Set `GOOGLE_SHEETS_SUBSCRIBERS_ID` to the sheet ID from its URL

---

## Usage

Each tool is a standalone script. Run them in sequence, or let Claude orchestrate everything via `workflows/newsletter.md`.

```bash
# 1. Research a topic
python tools/research.py \
  --topic "The rise of vertical AI agents" \
  --focus "enterprise adoption, key players, investment trends" \
  --depth basic

# 2. Write the newsletter
python tools/write_newsletter.py \
  --research .tmp/research_<slug>.json \
  --tone "analytical but accessible"

# 3. Generate charts
python tools/generate_charts.py --research .tmp/research_<slug>.json

# 4. Upload charts to Cloudinary
python tools/upload_images.py \
  --charts '<json from step 3>' \
  --topic-slug "<slug>"

# 5. Build the HTML email
python tools/build_html.py \
  --content .tmp/content_<slug>.json \
  --images '<json from step 4>' \
  --subject-index 0

# 6. Send a test to yourself first
python tools/send_newsletter.py \
  --html .tmp/newsletter_<slug>.html \
  --subject "Your chosen subject line" \
  --content .tmp/content_<slug>.json \
  --dry-run true

# 7. Send to full subscriber list
python tools/send_newsletter.py ... --dry-run false
```

Or just tell Claude: **"Write a newsletter about [topic]"** — it follows the full workflow in `workflows/newsletter.md` with human checkpoints at subject line selection, HTML review, and before the full send.

---

## The WAT framework

This project follows the **WAT architecture** (Workflows · Agents · Tools):

- **Workflows** (`workflows/`) — Plain-language SOPs that define objectives, tool sequence, quality checks, and error recovery. The instructions.
- **Agents** — Claude reads the workflow and orchestrates execution. Handles reasoning, decisions, and failures.
- **Tools** (`tools/`) — Python scripts that do the actual work: API calls, file transforms, email delivery. Deterministic and testable.

The separation matters: when AI tries to handle everything directly, accuracy compounds down with each step. Offloading execution to deterministic scripts keeps Claude focused on orchestration — where it's most reliable.

---

## Sending limits

| Service | Free tier |
|---|---|
| Tavily | 1,000 searches / month |
| Anthropic | Pay-as-you-go (one newsletter ≈ $0.05–0.15) |
| Cloudinary | 25 GB storage · 25 GB bandwidth / month |
| Gmail SMTP | 500 emails / day (standard) · 2,000 / day (Workspace) |

---

## License

MIT
