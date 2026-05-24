"""
write_newsletter.py — Take research JSON and produce all newsletter content via Claude.

Usage:
  python tools/write_newsletter.py --research .tmp/research_ai-in-healthcare.json
  python tools/write_newsletter.py --research .tmp/research_ai-in-healthcare.json --tone "casual and direct" --target-length long
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"

LENGTH_TARGETS = {"short": 400, "medium": 700, "long": 1000}

SYSTEM_PROMPT = """You are an expert newsletter writer. You write engaging, well-researched newsletters for a professional audience.
Given a research brief, produce all newsletter content as a single valid JSON object.
Return ONLY the JSON — no markdown fences, no explanation, no text outside the object.

The JSON must match this schema exactly:
{
  "topic": "string",
  "subject_lines": ["string", "string", "string"],
  "preheader_text": "string — 1 sentence, max 100 chars",
  "headline": "string — the chosen main headline",
  "subheadline": "string — supporting line under headline",
  "intro_paragraph": "string — 2-3 sentences drawing reader in",
  "sections": [
    {
      "section_id": "string — snake_case slug",
      "title": "string",
      "body": "string — 2-4 paragraphs of substance",
      "chart_ref": "string or null — must match a key from research chart_data",
      "key_stat": {"value": "string", "label": "string"} | null
    }
  ],
  "key_takeaways": ["string", "string", "string"],
  "cta": {
    "button_text": "string — action phrase, max 6 words",
    "url": "string — use the most relevant source URL from research, or null"
  },
  "sources": [{"title": "string", "url": "string or null"}],
  "plain_text_version": "string — complete newsletter as plain text"
}

Rules:
- subject_lines: exactly 3 options, each ≤50 characters, distinct angles (data-driven / curiosity / direct benefit)
- preheader_text: ≤100 characters, no period at end, makes reader want to open
- sections: 2-4 sections minimum, each with real substance not filler
- chart_ref values must exactly match keys from the research's chart_data dict, or be null
- key_takeaways: exactly 3 bullet-style insights a reader will remember
- plain_text_version: must be a complete readable version of the newsletter (not a summary)
- Write for the word count target provided
- Return ONLY the JSON object"""


def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:60]


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def write_content(research: dict, tone: str, word_count: int) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not found in .env")

    client = anthropic.Anthropic(api_key=api_key)

    chart_keys = list(research.get("chart_data", {}).keys())
    user_prompt = f"""Research brief:
{json.dumps(research, indent=2)}

Writing instructions:
- Tone: {tone}
- Target word count for body content: ~{word_count} words
- Available chart references (use these exact strings for chart_ref): {chart_keys if chart_keys else "none"}

Produce the complete newsletter content JSON now."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    try:
        data = extract_json(raw)
    except json.JSONDecodeError:
        # Response may have been truncated — retry with a request for shorter sections
        print("Warning: JSON parse failed, retrying with concise output request...", file=sys.stderr)
        repair_response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "The JSON above was cut off. Please regenerate it completely — keep section bodies shorter (2 paragraphs max each) so the entire response fits. Return ONLY valid JSON."},
            ],
        )
        data = extract_json(repair_response.content[0].text)

    return data


def validate(data: dict) -> list[str]:
    issues = []
    if len(data.get("subject_lines", [])) < 2:
        issues.append("fewer than 2 subject lines generated")
    for sl in data.get("subject_lines", []):
        if len(sl) > 55:
            issues.append(f"subject line too long ({len(sl)} chars): {sl}")
    if not data.get("preheader_text"):
        issues.append("missing preheader_text")
    if len(data.get("sections", [])) < 2:
        issues.append("fewer than 2 sections generated")
    if not data.get("plain_text_version"):
        issues.append("missing plain_text_version")
    return issues


def main():
    parser = argparse.ArgumentParser(description="Write newsletter content using Claude")
    parser.add_argument("--research", required=True, help="Path to research JSON file")
    parser.add_argument("--tone", default="analytical but accessible", help="Writing tone")
    parser.add_argument(
        "--target-length",
        default="medium",
        choices=["short", "medium", "long"],
        help="Target word count (default: medium ~700 words)",
    )
    args = parser.parse_args()

    research_path = Path(args.research)
    if not research_path.exists():
        sys.exit(f"Error: research file not found: {research_path}")

    research = json.loads(research_path.read_text())
    word_count = LENGTH_TARGETS[args.target_length]
    topic = research.get("topic", "newsletter")

    print(f"Writing newsletter for: {topic}", file=sys.stderr)
    data = write_content(research, args.tone, word_count)

    data["topic"] = topic
    data["generated_at"] = datetime.now(timezone.utc).isoformat()

    issues = validate(data)
    if issues:
        print(f"Warnings: {'; '.join(issues)}", file=sys.stderr)

    slug = slugify(topic)
    output_path = TMP_DIR / f"content_{slug}.json"
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    sections_count = len(data.get("sections", []))
    print(f"Generated {sections_count} sections, {len(data.get('subject_lines', []))} subject lines.", file=sys.stderr)
    print(str(output_path))


if __name__ == "__main__":
    main()
