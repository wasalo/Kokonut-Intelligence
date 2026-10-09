#!/usr/bin/env python3
"""Render registered workflow specifications into deterministic Markdown."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.workflow_specs.registry import list_specs
from services.workflow_specs.render import render_markdown, render_mermaid
from services.workflow_specs.validator import validate

DOCS = ROOT / "docs"


def main() -> None:
    for spec in list_specs():
        validate(spec)
        content = render_markdown(spec)
        content += "\n## Mermaid\n\n```mermaid\n"
        content += render_mermaid(spec)
        content += "```\n"
        path = DOCS / f"workflow-{spec.id.replace('_', '-')}.md"
        path.write_text(content)
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
