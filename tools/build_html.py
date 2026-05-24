"""
build_html.py — Render the Jinja2 email template with content + image URLs, inline CSS via premailer.

Usage:
  python tools/build_html.py --content .tmp/content_ai-in-healthcare.json --images '{}'
  python tools/build_html.py --content .tmp/content_ai-in-healthcare.json \
    --images '{"market_growth": "https://res.cloudinary.com/..."}' \
    --subject-index 1
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import logging
import warnings

import premailer
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Silence cssutils warnings about vendor-prefixed email CSS properties (intentional, not errors)
logging.getLogger("cssutils").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore", category=UserWarning, module="cssutils")

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TEMPLATES_DIR = BASE_DIR / "templates"


def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:60]


def main():
    parser = argparse.ArgumentParser(description="Build HTML email from content JSON + image URLs")
    parser.add_argument("--content", required=True, help="Path to content JSON from write_newsletter.py")
    parser.add_argument("--images", default="{}", help="JSON string: {chart_name: cloudinary_url}")
    parser.add_argument("--subject-index", type=int, default=0, choices=[0, 1, 2], help="Which subject line to use (0, 1, or 2)")
    args = parser.parse_args()

    content_path = Path(args.content)
    if not content_path.exists():
        sys.exit(f"Error: content file not found: {content_path}")

    template_path = TEMPLATES_DIR / "newsletter.html"
    if not template_path.exists():
        sys.exit(f"Error: template not found: {template_path}")

    content = json.loads(content_path.read_text())
    image_urls = json.loads(args.images)

    subject_lines = content.get("subject_lines", [])
    if not subject_lines:
        sys.exit("Error: content JSON has no subject_lines")

    idx = min(args.subject_index, len(subject_lines) - 1)
    chosen_subject = subject_lines[idx]

    # Template context
    ctx = {
        "headline": content.get("headline", ""),
        "subheadline": content.get("subheadline", ""),
        "preheader_text": content.get("preheader_text", ""),
        "intro_paragraph": content.get("intro_paragraph", ""),
        "sections": content.get("sections", []),
        "key_takeaways": content.get("key_takeaways", []),
        "cta": content.get("cta"),
        "sources": content.get("sources", []),
        "image_urls": image_urls,
        "newsletter_name": os.getenv("NEWSLETTER_FROM_NAME", "The Brief"),
        "sender_address": os.getenv("NEWSLETTER_SENDER_ADDRESS", ""),
        "unsubscribe_url": "{{ unsubscribe_url }}",  # placeholder; Resend injects this automatically
    }

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("newsletter.html")
    rendered = template.render(**ctx)

    # Inline all CSS via premailer (required for Outlook and broad client compatibility)
    try:
        inlined = premailer.transform(
            rendered,
            remove_classes=False,
            strip_important=False,
            allow_network=False,
            base_url=None,
        )
    except Exception as e:
        print(f"Warning: premailer failed ({e}), saving unprocessed HTML.", file=sys.stderr)
        inlined = rendered

    topic = content.get("topic", "newsletter")
    slug = slugify(topic)
    output_path = TMP_DIR / f"newsletter_{slug}.html"
    output_path.write_text(inlined, encoding="utf-8")

    print(f"HTML saved: {output_path}", file=sys.stderr)
    print(f"Subject: {chosen_subject}", file=sys.stderr)
    print(f"Preheader: {content.get('preheader_text', '')}", file=sys.stderr)

    # Stdout: machine-readable summary for the workflow
    print(json.dumps({
        "html_path": str(output_path),
        "subject": chosen_subject,
        "preheader": content.get("preheader_text", ""),
        "topic": topic,
    }))


if __name__ == "__main__":
    main()
