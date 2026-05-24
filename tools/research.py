"""
research.py — Search via Tavily API, then structure results into research JSON using Claude.

Usage:
  python tools/research.py --topic "AI in healthcare" --focus "costs, adoption, key players"
  python tools/research.py --topic "AI in healthcare" --depth advanced
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
from tavily import TavilyClient

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TMP_DIR.mkdir(exist_ok=True)

STRUCTURING_PROMPT = """You are a research assistant preparing content for a professional newsletter.
Given raw web search results on a topic, produce a comprehensive research brief as a valid JSON object.
Return ONLY the JSON — no markdown fences, no text outside the object.

The JSON must match this schema exactly:
{
  "topic": "string",
  "focus_areas": ["string"],
  "key_findings": [
    {
      "finding": "string — one concrete, specific insight",
      "significance": "string — why it matters",
      "source_url": "string or null",
      "source_name": "string or null"
    }
  ],
  "statistics": [
    {
      "label": "string",
      "value": number,
      "unit": "string",
      "chart_eligible": boolean
    }
  ],
  "narrative_summary": "string — 2-3 paragraph synthesis of the overall landscape",
  "key_players": ["string"],
  "chart_data": {
    "<chart_slug>": {
      "type": "bar | line | pie | horizontal_bar",
      "title": "string",
      "x_labels": ["string"],
      "values": [number],
      "x_axis_label": "string",
      "y_axis_label": "string"
    }
  },
  "sources": [
    {"title": "string", "url": "string or null", "publisher": "string or null"}
  ]
}

Rules:
- Include at least 4 key_findings with real specifics drawn from the search results.
- Include at least 2 statistics where chart_eligible is true when quantitative data exists.
- Include at least 1 entry in chart_data when quantitative trends are available.
- chart_data keys must be snake_case slugs (e.g. "market_growth", "adoption_rates").
- All values in chart arrays must be numbers (no strings, no nulls).
- x_labels and values arrays must be the same length.
- Return ONLY the JSON object — no markdown, no explanation."""


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


def search_tavily(topic: str, focus: str, depth: str) -> dict:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        sys.exit("Error: TAVILY_API_KEY not found in .env")

    client = TavilyClient(api_key=api_key)
    query = f"{topic} {focus}".strip() if focus else topic

    result = client.search(
        query=query,
        search_depth=depth,
        max_results=8,
        include_answer=True,
    )
    return result


def structure_with_claude(topic: str, focus: str, tavily_result: dict) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not found in .env")

    client = anthropic.Anthropic(api_key=api_key)

    # Build a compact representation of Tavily results for the prompt
    results_text = []
    if tavily_result.get("answer"):
        results_text.append(f"AI Summary: {tavily_result['answer']}\n")

    for i, r in enumerate(tavily_result.get("results", []), 1):
        results_text.append(
            f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('content', '')}\n"
        )

    user_prompt = f"""Topic: {topic}
{"Focus areas: " + focus if focus else ""}

Web search results:
{"---".join(results_text)}

Using the search results above, produce the structured research JSON brief now."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=STRUCTURING_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    try:
        return extract_json(raw)
    except json.JSONDecodeError:
        print("Warning: JSON parse failed on first attempt, retrying...", file=sys.stderr)
        repair = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system="Return ONLY a valid JSON object. Fix any syntax errors and return the corrected JSON.",
            messages=[{"role": "user", "content": raw}],
        )
        return extract_json(repair.content[0].text)


def main():
    parser = argparse.ArgumentParser(description="Research a topic using Tavily search + Claude structuring")
    parser.add_argument("--topic", required=True, help="Newsletter topic to research")
    parser.add_argument("--focus", default="", help="Comma-separated focus areas (appended to search query)")
    parser.add_argument(
        "--depth",
        default="basic",
        choices=["basic", "advanced"],
        help="Tavily search depth: basic (1 credit) or advanced (2 credits). Default: basic",
    )
    args = parser.parse_args()

    print(f"Searching Tavily [{args.depth}]: {args.topic}", file=sys.stderr)
    tavily_result = search_tavily(args.topic, args.focus, args.depth)
    print(f"Got {len(tavily_result.get('results', []))} results. Structuring with Claude...", file=sys.stderr)

    data = structure_with_claude(args.topic, args.focus, tavily_result)

    data["topic"] = args.topic
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    if args.focus and "focus_areas" not in data:
        data["focus_areas"] = [f.strip() for f in args.focus.split(",")]

    findings_count = len(data.get("key_findings", []))
    charts_count = len(data.get("chart_data", {}))
    print(f"Found {findings_count} key findings, {charts_count} chart datasets.", file=sys.stderr)

    if findings_count < 3:
        print("Warning: fewer than 3 key findings — research may be thin.", file=sys.stderr)

    slug = slugify(args.topic)
    output_path = TMP_DIR / f"research_{slug}.json"
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    print(str(output_path))


if __name__ == "__main__":
    main()
