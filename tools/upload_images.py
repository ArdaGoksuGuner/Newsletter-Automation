"""
upload_images.py — Upload local chart PNGs to Cloudinary and return public URLs.

Usage:
  python tools/upload_images.py --charts '{"market_growth": "/abs/path/to/market_growth.png"}'
  python tools/upload_images.py --charts '{}' --folder "newsletters/2026"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()


def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:60]


def main():
    parser = argparse.ArgumentParser(description="Upload chart PNGs to Cloudinary")
    parser.add_argument("--charts", required=True, help="JSON string: {chart_name: local_file_path}")
    parser.add_argument("--folder", default="newsletters", help="Cloudinary folder (default: newsletters)")
    parser.add_argument("--topic-slug", default="", help="Topic slug for namespacing public_ids")
    args = parser.parse_args()

    charts = json.loads(args.charts)
    if not charts:
        print("{}")
        return

    required_keys = ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        sys.exit(f"Error: missing Cloudinary credentials in .env: {', '.join(missing)}")

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )

    results = {}
    topic_prefix = f"{slugify(args.topic_slug)}_" if args.topic_slug else ""

    for chart_name, local_path in charts.items():
        path = Path(local_path)
        if not path.exists():
            print(f"Warning: file not found for '{chart_name}': {local_path}", file=sys.stderr)
            continue

        public_id = f"{args.folder}/{topic_prefix}{chart_name}"

        try:
            result = cloudinary.uploader.upload(
                str(path),
                public_id=public_id,
                overwrite=True,
                resource_type="image",
            )
            url = result["secure_url"]
            results[chart_name] = url
            print(f"Uploaded: {chart_name} → {url}", file=sys.stderr)
        except Exception as e:
            # Retry once
            print(f"Upload failed for '{chart_name}', retrying... ({e})", file=sys.stderr)
            try:
                result = cloudinary.uploader.upload(
                    str(path),
                    public_id=public_id,
                    overwrite=True,
                    resource_type="image",
                )
                results[chart_name] = result["secure_url"]
                print(f"Retry succeeded: {chart_name}", file=sys.stderr)
            except Exception as e2:
                print(f"Error: upload failed for '{chart_name}': {e2}", file=sys.stderr)

    print(json.dumps(results))


if __name__ == "__main__":
    main()
