"""L rules: layout and style.

Planned, not implemented yet (codes reserved):
  L03 component-unchanged  - needs the components/ system
  L06 explicit-labels      - headers and tooltips carry explicit labels
"""

from __future__ import annotations

import re

from ..definition import iter_visuals, layout_elements, px, walk
from . import rule

HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")


@rule("L01", "canvas-width", "error", "Every sheet uses the standard canvas width.")
def l01(ctx):
    want = int(ctx.cfg["grid"]["canvas_width"])
    for sheet in ctx.defn.get("Sheets") or []:
        for layout in sheet.get("Layouts") or []:
            config = layout.get("Configuration") or {}
            for ltype in ("FreeFormLayout", "GridLayout"):
                opts = ((config.get(ltype) or {}).get("CanvasSizeOptions") or {}).get("ScreenCanvasSizeOptions") or {}
                width = px(opts.get("OptimizedViewPortWidth"))
                if width is not None and width != want:
                    yield f"sheet {sheet['SheetId']}", f"canvas {width}px, expected {want}px"


@rule("L02", "on-grid", "error", "Every free-form element's position and size sit on the grid step.")
def l02(ctx):
    step = int(ctx.cfg["grid"]["step"])
    for sheet in ctx.defn.get("Sheets") or []:
        for ltype, el in layout_elements(sheet):
            if ltype != "FreeFormLayout":
                continue
            off = []
            for key in ("XAxisLocation", "YAxisLocation", "Width", "Height"):
                value = px(el.get(key))
                if value is not None and value % step:
                    off.append(f"{key}={value}")
            if off:
                yield el["ElementId"], f"off the {step}px grid: {', '.join(off)}"


@rule("L04", "theme-colors", "warn", "No hex colors in visuals or text boxes; colors come from the theme.")
def l04(ctx):
    for _, _, body in iter_visuals(ctx.defn):
        colors = {m for _, node in walk(body) if isinstance(node, str) for m in HEX.findall(node)}
        if colors:
            yield body["VisualId"], f"{len(colors)} hard-coded color(s): {', '.join(sorted(colors)[:5])}"
    for sheet in ctx.defn.get("Sheets") or []:
        for tb in sheet.get("TextBoxes") or []:
            colors = set(HEX.findall(tb.get("Content") or ""))
            if colors:
                yield tb["SheetTextBoxId"], f"{len(colors)} hard-coded color(s): {', '.join(sorted(colors)[:5])}"


@rule("L05", "theme-type-scale", "warn", "Absolute font sizes come from the theme's type scale.")
def l05(ctx):
    allowed = {int(s) for s in ctx.cfg["theme"]["font_sizes"]}
    if not allowed:
        return
    for sheet in ctx.defn.get("Sheets") or []:
        for path, node in walk(sheet):
            if path and path[-1] == "Absolute" and "FontSize" in path:
                size = px(node)
                if size is not None and size not in allowed:
                    yield f"sheet {sheet['SheetId']}", f"font size {size}px not in {sorted(allowed)}"
