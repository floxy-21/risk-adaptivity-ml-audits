#!/usr/bin/env python3
"""Generate the standalone vector visual abstract using only Python's stdlib.

Run from any directory:
  python make_summary_svg.py --output outputs/precision_boundary_summary.svg

The default output resolves from this file to the repository outputs folder.
The SVG embeds no raster images, fonts, scripts, or external dependencies.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

INK = "#18313F"
MUTED = "#526773"
TEAL = "#087F83"
BLUE = "#315A79"
GOLD = "#9A6829"


def tag(parent, name, **attrs):
    return ET.SubElement(parent, f"{{{SVG}}}{name}",
                         {key.replace("_", "-"): str(value) for key, value in attrs.items()})


def text(parent, x, y, content, size=20, weight=400, fill=INK, anchor="start", spacing=None):
    attrs = dict(x=x, y=y, font_size=size, font_weight=weight, fill=fill, text_anchor=anchor)
    if spacing is not None:
        attrs["letter_spacing"] = spacing
    node = tag(parent, "text", **attrs)
    node.text = content
    return node


def line(parent, x1, y1, x2, y2, color, width=1.5, **attrs):
    return tag(parent, "line", x1=x1, y1=y1, x2=x2, y2=y2,
               stroke=color, stroke_width=width, **attrs)


def rect(parent, x, y, width, height, fill, stroke="none", radius=16):
    return tag(parent, "rect", x=x, y=y, width=width, height=height,
               rx=radius, fill=fill, stroke=stroke, stroke_width=1.2)


def arrow(parent, x1, y, x2, color):
    line(parent, x1, y, x2 - 8, y, color, 2)
    tag(parent, "path", d=f"M {x2 - 14} {y - 6} L {x2 - 7} {y} L {x2 - 14} {y + 6}",
        fill="none", stroke=color, stroke_width=2, stroke_linecap="round", stroke_linejoin="round")


def build_svg():
    root = ET.Element(f"{{{SVG}}}svg", {
        "width": "1440", "height": "1050", "viewBox": "0 0 1440 1050",
        "role": "img", "aria-labelledby": "summary-title summary-description",
        "font-family": "Arial, Helvetica, sans-serif",
    })
    title = tag(root, "title", id="summary-title")
    title.text = "Sharing two readings changes the precision guarantee"
    desc = tag(root, "desc", id="summary-description")
    desc.text = (
        "Visual abstract. For one affine comparison on a compact convex uncertainty set, "
        "a deterministic adaptive two-query precision guarantee implies some randomized "
        "fixed batch has worst-record success at least one half. In a constructed family "
        "with two jointly audited contrasts and m at least three, optimal worst-record "
        "success is one for adaptation and exactly one over m for randomized fixed batches. "
        "All m plus three coordinates are available as exact unit-cost queries, so dimension "
        "and query dictionary grow with m. Each contrast separately needs only two fixed "
        "queries; three fixed queries suffice jointly. The separation also covers all three "
        "pairwise comparisons among three models. Separately, source-derived meter blocks "
        "have verified success one versus one half on 165 of 819 original blocks and 57 of "
        "279 external blocks, under the declared exact-total and noiseless-prefix query model. "
        "These are exact instance certificates, not recorded success-rate estimates or a "
        "universal deployment-gain claim."
    )
    rect(root, 0, 0, 1440, 1050, "#FFFFFF", radius=0)

    text(root, 64, 53, "PRECISION UNDER A SHARED QUERY BUDGET", 17, 700, MUTED, spacing=1.8)
    text(root, 64, 111, "Sharing two readings changes", 46, 700)
    text(root, 64, 165, "the precision guarantee", 46, 700)
    text(root, 64, 205, "Affine contrasts · compact convex uncertainty · finite dictionary of exact scalar queries", 21, 400, MUTED)

    # The general scalar theorem is visually distinct from the constructed family.
    rect(root, 64, 238, 596, 408, "#F3F6F9", "#DCE4EA")
    rect(root, 684, 238, 692, 408, "#EFF8F6", "#CFE4DE")
    text(root, 94, 276, "GENERAL GUARANTEE", 16, 700, BLUE, spacing=1.4)
    text(root, 94, 321, "One comparison", 31, 700)
    text(root, 201, 414, "1", 72, 700, BLUE, "middle")
    arrow(root, 295, 390, 377, BLUE)
    text(root, 493, 414, "≥ 1/2", 66, 700, BLUE, "middle")
    text(root, 201, 452, "adaptive", 21, 400, INK, "middle")
    text(root, 201, 481, "guarantee", 21, 400, INK, "middle")
    text(root, 493, 452, "randomized fixed", 21, 400, INK, "middle")
    text(root, 493, 481, "batch guarantee", 21, 400, INK, "middle")
    line(root, 94, 517, 630, 517, "#D4DFE6")
    text(root, 94, 552, "If two adaptive readings ensure precision,", 21)
    text(root, 94, 583, "a randomized batch retains a half-success floor.", 21)
    text(root, 94, 621, "Premise: deterministic adaptive policy", 17, 400, MUTED)

    text(root, 714, 276, "CONSTRUCTED FAMILY · m ≥ 3", 16, 700, TEAL, spacing=1.2)
    text(root, 714, 321, "Two contrasts audited jointly", 31, 700)
    text(root, 714, 348, "Success = halve both sharp interval widths", 17, 400, MUTED)
    text(root, 848, 414, "1", 72, 700, TEAL, "middle")
    text(root, 1026, 396, "vs", 23, 400, MUTED, "middle")
    text(root, 1198, 414, "1/m", 72, 700, TEAL, "middle")
    text(root, 848, 452, "adaptive", 21, 400, INK, "middle")
    text(root, 848, 481, "success", 21, 400, INK, "middle")
    text(root, 1198, 452, "optimal randomized", 21, 400, INK, "middle")
    text(root, 1198, 481, "fixed batch", 21, 400, INK, "middle")
    line(root, 714, 517, 1346, 517, "#C8DFD8")

    # A small branching query tree makes feedback concrete without a dense formula.
    for y in (542, 568, 594):
        line(root, 786, 568, 863, y, "#6DADA3", 1.8)
    tag(root, "circle", cx=776, cy=568, r=19, fill="#FFFFFF", stroke=TEAL, stroke_width=1.5)
    text(root, 776, 575, "t", 21, 700, TEAL, "middle")
    for y, label in ((542, "z₁"), (568, "zⱼ"), (594, "zₘ")):
        rect(root, 863, y - 12, 42, 25, "#FFFFFF", "#8BBDB2", radius=5)
        text(root, 884, y + 7, label, 18, 400, TEAL, "middle")
    text(root, 936, 559, "The first answer selects", 20)
    text(root, 936, 588, "the second reading.", 20)
    text(root, 714, 621, "Exact unit-cost coordinates · dimension/dictionary grow with m", 17, 400, MUTED)

    # Scope statements belong to the theorem, outside the separate data panel.
    text(root, 64, 690, "Same two-reading budget. Success is measured on the worst feasible record.", 21, 700)
    text(root, 64, 724, "Joint family: 2 fixed readings suffice for each contrast; 3 suffice for joint assurance.", 20, 400, MUTED)
    text(root, 64, 754, "The same separation holds for all 3 pairwise comparisons among 3 models.", 20, 400, MUTED)

    # Source-derived instance certificates are not mixed with theorem claims or replay rates.
    rect(root, 64, 792, 1312, 202, "#FCF7EE", "#E8DDCA")
    text(root, 94, 830, "METER APPLICATION · EXACT INSTANCE CERTIFICATES", 16, 700, GOLD, spacing=1.2)
    text(root, 94, 902, "1 vs 1/2", 54, 700, GOLD)
    text(root, 94, 935, "adaptive / optimal randomized batch", 19, 400, INK)
    line(root, 625, 850, 625, 942, "#DFD0B8")
    text(root, 821, 895, "165 / 819", 43, 700, INK, "middle")
    text(root, 821, 930, "certified original blocks", 20, 400, MUTED, "middle")
    text(root, 1187, 895, "57 / 279", 43, 700, INK, "middle")
    text(root, 1187, 930, "certified external blocks", 20, 400, MUTED, "middle")
    text(root, 94, 970, "Declared query model: exact total + noiseless prefixes · two readings · all six model pairs", 18, 400, MUTED)
    text(root, 64, 1027, "Retrospective, instance-specific evidence under declared access rules; no universal deployment gain.", 18, 400, MUTED)

    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parents[3] / "outputs" / "precision_boundary_summary.svg"
    parser.add_argument("--output", type=Path, default=default)
    args = parser.parse_args()
    root = build_svg()
    ET.indent(root, space="  ")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(args.output, encoding="utf-8", xml_declaration=True)
    parsed = ET.parse(args.output)
    assert parsed.getroot().tag == f"{{{SVG}}}svg"
    assert parsed.getroot().attrib["viewBox"] == "0 0 1440 1050"
    assert not parsed.findall(f".//{{{SVG}}}image")
    assert not parsed.findall(f".//{{{SVG}}}script")
    print(f"Wrote valid standalone SVG: {args.output.resolve()}")


if __name__ == "__main__":
    main()
