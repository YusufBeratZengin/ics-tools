"""Generate docs/demo.svg terminal recording from real CLI executions."""

from __future__ import annotations

import html
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"
OUTPUT_SVG = DOCS_DIR / "demo.svg"


def run_cli_cmd(args: list[str]) -> str:
    """Run CLI command and return stdout decoded."""
    cmd = [sys.executable, "-m", "ics_tools", *args]
    res = subprocess.run(  # noqa: S603
        cmd,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def build_demo_lines() -> list[tuple[str, str]]:
    """Build list of (line_type, text) pairs.
    line_type: 'cmd', 'output', 'success', 'dim', 'empty'
    """
    lines: list[tuple[str, str]] = []

    # 1. Validate
    lines.append(("cmd", "ics validate examples/demo.ics"))
    val_out = run_cli_cmd(["validate", "examples/demo.ics"])
    lines.append(("success", val_out))

    lines.append(("empty", ""))

    # 2. List
    lines.append(("cmd", "ics list examples/demo.ics --from 2026-01-01 --window 7d"))
    list_out = run_cli_cmd(["list", "examples/demo.ics", "--from", "2026-01-01", "--window", "7d"])
    for i, line in enumerate(list_out.splitlines()):
        if i in (0, 1):
            lines.append(("dim", line))
        else:
            lines.append(("output", line))

    lines.append(("empty", ""))

    # 3. to-csv
    lines.append(("cmd", "ics to-csv examples/demo.ics --from 2026-01-01 --window 7d"))
    csv_out = run_cli_cmd(["to-csv", "examples/demo.ics", "--from", "2026-01-01", "--window", "7d"])
    for i, line in enumerate(csv_out.splitlines()):
        if i == 0:
            lines.append(("dim", line))
        else:
            lines.append(("output", line))

    return lines


def generate_svg(lines: list[tuple[str, str]], output_path: Path) -> None:
    width = 860
    line_height = 22
    pad_top = 56
    pad_bottom = 24
    height = pad_top + (len(lines) * line_height) + pad_bottom

    color_map = {
        "prompt": "#7ee787",
        "cmd": "#f0f6fc",
        "output": "#c9d1d9",
        "success": "#3fb950",
        "dim": "#8b949e",
    }

    spans: list[str] = []
    curr_y = pad_top + 16

    for line_type, text in lines:
        escaped = html.escape(text)
        if line_type == "cmd":
            span = (
                f'<text x="24" y="{curr_y}" fill="{color_map["prompt"]}" font-weight="600">$ </text>'
                f'<text x="40" y="{curr_y}" fill="{color_map["cmd"]}" font-weight="600">{escaped}</text>'
            )
            spans.append(span)
        elif line_type == "empty":
            pass
        else:
            color = color_map.get(line_type, color_map["output"])
            weight = "bold" if line_type == "success" else "normal"
            span = f'<text x="24" y="{curr_y}" fill="{color}" font-weight="{weight}">{escaped}</text>'
            spans.append(span)
        curr_y += line_height

    content = "\n  ".join(spans)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="auto">
  <defs>
    <style>
      .term-text {{
        font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
        font-size: 13.5px;
        letter-spacing: 0.2px;
      }}
      .window-header {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 12px;
        font-weight: 500;
        fill: #8b949e;
      }}
    </style>
    <linearGradient id="bg-grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#161b22"/>
    </linearGradient>
  </defs>

  <!-- Window Container -->
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" ry="10" fill="url(#bg-grad)" stroke="#30363d" stroke-width="1"/>

  <!-- Title bar -->
  <line x1="0" y1="38" x2="{width}" y2="38" stroke="#21262d" stroke-width="1"/>
  <circle cx="20" cy="19" r="6" fill="#ff5f56"/>
  <circle cx="38" cy="19" r="6" fill="#ffbd2e"/>
  <circle cx="56" cy="19" r="6" fill="#27c93f"/>
  <text x="{width // 2}" y="24" text-anchor="middle" class="window-header">ics-tools — CLI Demo</text>

  <!-- Terminal Content -->
  <g class="term-text">
  {content}
  </g>
</svg>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    print(f"Generated {output_path} ({len(lines)} lines, {width}x{height})")


def main() -> None:
    lines = build_demo_lines()
    generate_svg(lines, OUTPUT_SVG)


if __name__ == "__main__":
    main()
