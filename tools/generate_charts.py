"""
generate_charts.py — Generate matplotlib chart PNGs from research JSON chart_data.

Usage:
  python tools/generate_charts.py --research .tmp/research_ai-in-healthcare.json
  python tools/generate_charts.py --research .tmp/research_ai-in-healthcare.json --style dark
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
CHARTS_DIR = BASE_DIR / ".tmp" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Color palettes
THEMES = {
    "light": {
        "bg": "#ffffff",
        "text": "#1a1a2e",
        "accent": "#4361ee",
        "accent2": "#7209b7",
        "grid": "#e0e0e0",
        "bar_colors": ["#4361ee", "#7209b7", "#f72585", "#3a86ff", "#06d6a0"],
    },
    "dark": {
        "bg": "#1a1a2e",
        "text": "#f0f0f0",
        "accent": "#7b9cff",
        "accent2": "#c77dff",
        "grid": "#2d2d50",
        "bar_colors": ["#7b9cff", "#c77dff", "#ff6b9d", "#5bc0eb", "#4ecdc4"],
    },
}


def apply_style(ax, fig, theme: dict, title: str, x_label: str, y_label: str):
    fig.patch.set_facecolor(theme["bg"])
    ax.set_facecolor(theme["bg"])

    ax.set_title(title, color=theme["text"], fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel(x_label, color=theme["text"], fontsize=11)
    ax.set_ylabel(y_label, color=theme["text"], fontsize=11)

    ax.tick_params(colors=theme["text"], labelsize=10)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(theme["grid"])

    ax.yaxis.grid(True, color=theme["grid"], alpha=0.6, linewidth=0.8)
    ax.set_axisbelow(True)

    ax.tick_params(axis="x", colors=theme["text"])
    ax.tick_params(axis="y", colors=theme["text"])


def chart_bar(data: dict, theme: dict, out_path: Path):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4), dpi=150)
    colors = theme["bar_colors"][: len(data["values"])]
    bars = ax.bar(data["x_labels"], data["values"], color=colors, width=0.6, edgecolor="none")

    # Value labels on top of bars
    for bar, val in zip(bars, data["values"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(data["values"]) * 0.01,
            str(val),
            ha="center",
            va="bottom",
            color=theme["text"],
            fontsize=9,
            fontweight="bold",
        )

    apply_style(ax, fig, theme, data["title"], data.get("x_axis_label", ""), data.get("y_axis_label", ""))
    plt.tight_layout(pad=1.5)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=theme["bg"])
    plt.close()


def chart_line(data: dict, theme: dict, out_path: Path):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4), dpi=150)
    ax.plot(
        data["x_labels"],
        data["values"],
        color=theme["accent"],
        linewidth=2.5,
        marker="o",
        markersize=6,
        markerfacecolor=theme["accent2"],
        markeredgewidth=0,
    )
    ax.fill_between(data["x_labels"], data["values"], alpha=0.12, color=theme["accent"])

    apply_style(ax, fig, theme, data["title"], data.get("x_axis_label", ""), data.get("y_axis_label", ""))
    plt.tight_layout(pad=1.5)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=theme["bg"])
    plt.close()


def chart_horizontal_bar(data: dict, theme: dict, out_path: Path):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, max(3, len(data["x_labels"]) * 0.6)), dpi=150)
    colors = theme["bar_colors"][: len(data["values"])]
    bars = ax.barh(data["x_labels"], data["values"], color=colors, edgecolor="none")

    for bar, val in zip(bars, data["values"]):
        ax.text(
            bar.get_width() + max(data["values"]) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center",
            color=theme["text"],
            fontsize=9,
            fontweight="bold",
        )

    apply_style(ax, fig, theme, data["title"], data.get("y_axis_label", ""), data.get("x_axis_label", ""))
    ax.invert_yaxis()
    plt.tight_layout(pad=1.5)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=theme["bg"])
    plt.close()


def chart_pie(data: dict, theme: dict, out_path: Path):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    colors = theme["bar_colors"][: len(data["values"])]
    wedges, texts, autotexts = ax.pie(
        data["values"],
        labels=data["x_labels"],
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"edgecolor": theme["bg"], "linewidth": 2},
    )
    for text in texts:
        text.set_color(theme["text"])
    for autotext in autotexts:
        autotext.set_color(theme["bg"])
        autotext.set_fontweight("bold")

    ax.set_title(data["title"], color=theme["text"], fontsize=14, fontweight="bold", pad=15)
    fig.patch.set_facecolor(theme["bg"])
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=theme["bg"])
    plt.close()


CHART_BUILDERS = {
    "bar": chart_bar,
    "line": chart_line,
    "horizontal_bar": chart_horizontal_bar,
    "pie": chart_pie,
}


def main():
    parser = argparse.ArgumentParser(description="Generate chart PNGs from research JSON")
    parser.add_argument("--research", required=True, help="Path to research JSON file")
    parser.add_argument("--style", default="light", choices=["light", "dark"], help="Chart color theme")
    args = parser.parse_args()

    research_path = Path(args.research)
    if not research_path.exists():
        sys.exit(f"Error: research file not found: {research_path}")

    research = json.loads(research_path.read_text())
    chart_data = research.get("chart_data", {})

    if not chart_data:
        print("No chart_data found in research JSON — skipping chart generation.", file=sys.stderr)
        print("{}")
        return

    theme = THEMES[args.style]
    results = {}

    for chart_name, data in chart_data.items():
        chart_type = data.get("type", "bar")
        builder = CHART_BUILDERS.get(chart_type)

        if not builder:
            print(f"Warning: unsupported chart type '{chart_type}' for '{chart_name}' — skipping.", file=sys.stderr)
            continue

        if not data.get("x_labels") or not data.get("values"):
            print(f"Warning: missing x_labels or values for '{chart_name}' — skipping.", file=sys.stderr)
            continue

        if len(data["x_labels"]) != len(data["values"]):
            print(f"Warning: x_labels/values length mismatch for '{chart_name}' — skipping.", file=sys.stderr)
            continue

        out_path = CHARTS_DIR / f"{chart_name}.png"
        try:
            builder(data, theme, out_path)
            results[chart_name] = str(out_path.resolve())
            print(f"Generated: {out_path.name}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: failed to generate '{chart_name}': {e}", file=sys.stderr)

    print(json.dumps(results))


if __name__ == "__main__":
    main()
