"""Thread/async-safe result collection + rich CLI report renderer."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

STATUS_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}


@dataclass
class Finding:
    check: str
    status: str            # PASS / WARN / FAIL
    detail: str = ""
    data: Any = None


@dataclass
class ModuleReport:
    module: str
    started: float = field(default_factory=time.time)
    findings: list[Finding] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, check: str, status: str, detail: str = "", data: Any = None) -> None:
        with self._lock:
            self.findings.append(Finding(check, status.upper(), detail, data))

    def metric(self, key: str, value: float) -> None:
        with self._lock:
            self.metrics[key] = value

    @property
    def elapsed(self) -> float:
        return time.time() - self.started

    def count(self, status: str) -> int:
        return sum(1 for f in self.findings if f.status == status)

    @property
    def worst(self) -> str:
        if any(f.status == "FAIL" for f in self.findings):
            return "FAIL"
        if any(f.status == "WARN" for f in self.findings):
            return "WARN"
        return "PASS"


def render(reports: list[ModuleReport], console: Any, verbose: bool = False) -> None:
    from rich.table import Table
    from rich.panel import Panel

    for rep in reports:
        table = Table(
            title=f"[bold]{rep.module}[/]  ({rep.elapsed:.1f}s)",
            show_lines=False,
            header_style="bold cyan",
        )
        table.add_column("Result", width=6)
        table.add_column("Check", ratio=2)
        table.add_column("Detail", ratio=5, overflow="fold")
        shown = rep.findings
        fails_only = [f for f in shown if f.status != "PASS"]
        if not verbose and len(shown) > 60:
            table.add_row("", f"[dim]{len(shown)} checks total; showing non-PASS[/]", "")
            shown = fails_only[:80]
        for f in shown:
            color = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}.get(f.status, "white")
            table.add_row(f"[{color}]{f.status}[/]", f.check, f.detail)
        console.print(table)
        if rep.metrics:
            mt = Table(show_header=False, box=None, pad_edge=False)
            mt.add_column("k", ratio=1)
            mt.add_column("v", ratio=3)
            for k, v in sorted(rep.metrics.items()):
                pretty = f"{v:,.0f}" if isinstance(v, (int, float)) and abs(v) >= 1000 else (f"{v:,.4g}" if isinstance(v, (int, float)) else str(v))
                mt.add_row(k, pretty)
            console.print(
                Panel(mt, title=f"[bold]{rep.module} metrics[/]", expand=False)
            )
        for art in rep.artifacts:
            console.print(f"  artifact: [underline]{art}[/]")

    summary = Table(title="[bold]SUMMARY[/]", header_style="bold cyan")
    summary.add_column("Module", ratio=2)
    summary.add_column("PASS", justify="right")
    summary.add_column("WARN", justify="right")
    summary.add_column("FAIL", justify="right")
    summary.add_column("Status", justify="center")
    totals = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for rep in reports:
        p, w, x = rep.count("PASS"), rep.count("WARN"), rep.count("FAIL")
        for k, v in (("PASS", p), ("WARN", w), ("FAIL", x)):
            totals[k] += v
        color = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}[rep.worst]
        summary.add_row(rep.module, str(p), str(w), str(x), f"[{color}][bold]{rep.worst}[/]")
    console.print(summary)
    color = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}[
        "FAIL" if totals["FAIL"] else ("WARN" if totals["WARN"] else "PASS")
    ]
    console.print(
        Panel(
            f"[{color}][bold]{totals['FAIL']} FAIL / {totals['WARN']} WARN / {totals['PASS']} PASS[/]",
            title="OMNITEST RESULT", expand=False,
        )
    )


def exit_code(reports: list[ModuleReport]) -> int:
    if any(r.worst == "FAIL" for r in reports):
        return 2
    if any(r.worst == "WARN" for r in reports):
        return 1
    return 0


def export_json(reports: list[ModuleReport], path: str) -> str:
    """Write all findings to a JSON file; return the path written."""
    import json, time, os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "modules": [],
    }
    for rep in reports:
        mod = {
            "module": rep.module,
            "elapsed_s": round(rep.elapsed, 2),
            "status": rep.worst,
            "metrics": dict(rep.metrics),
            "artifacts": list(rep.artifacts),
            "findings": [
                {"check": f.check, "status": f.status, "detail": f.detail}
                for f in rep.findings
            ],
        }
        payload["modules"].append(mod)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def export_csv(reports: list[ModuleReport], path: str) -> str:
    """Write all findings to a CSV file; return the path written."""
    import csv, time, os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp", "module", "check", "status", "detail"])
        for rep in reports:
            for f in rep.findings:
                w.writerow([ts, rep.module, f.check, f.status, f.detail])
    return path


def build_collage(artifacts_dir: str, out_path: str, cols: int = 6,
                  thumb_w: int = 200, thumb_h: int = 120, padding: int = 4) -> str:
    """Stitch every games/<id>.png into a labelled grid collage."""
    import os, glob
    from PIL import Image, ImageDraw, ImageFont

    game_dir = os.path.join(artifacts_dir, "games")
    shots = sorted(glob.glob(os.path.join(game_dir, "*.png")))
    if not shots:
        return ""
    rows_count = (len(shots) + cols - 1) // cols
    cell_w = thumb_w + padding
    cell_h = thumb_h + 20 + padding          # 20px label bar
    canvas = Image.new("RGB", (cols * cell_w, rows_count * cell_h), (30, 30, 30))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 11)
    except Exception:
        font = ImageFont.load_default()
    for i, shot in enumerate(shots):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_w, r * cell_h
        try:
            im = Image.open(shot).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
            canvas.paste(im, (x0, y0 + 18))
        except Exception:
            draw.rectangle([x0, y0 + 18, x0 + thumb_w, y0 + 18 + thumb_h],
                           fill=(50, 50, 50))
        label = os.path.splitext(os.path.basename(shot))[0]
        draw.rectangle([x0, y0, x0 + thumb_w, y0 + 17], fill=(20, 20, 20))
        draw.text((x0 + 3, y0 + 2), label, fill=(0, 220, 255), font=font)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    canvas.save(out_path, optimize=True)
    return out_path
