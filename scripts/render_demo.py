"""Renders docs/demo.svg from a real run on examples/demo.

uv run --with rich python scripts/render_demo.py
"""

import contextlib
import io
from pathlib import Path

from rich.console import Console
from rich.text import Text

from adk_upgrade_check.cli import main

ROOT = Path(__file__).resolve().parent.parent

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
  main([str(ROOT / "examples" / "demo"), "--color", "always"])
output = buf.getvalue().replace(str(ROOT / "examples" / "demo"), "examples/demo")

console = Console(record=True, width=118, file=io.StringIO())
console.print(Text("$ adk-upgrade-check examples/demo", style="bold"))
console.print(Text.from_ansi(output.rstrip()))
(ROOT / "docs" / "demo.svg").write_text(
    console.export_svg(title="adk-upgrade-check"), encoding="utf-8"
)
print("wrote docs/demo.svg")
