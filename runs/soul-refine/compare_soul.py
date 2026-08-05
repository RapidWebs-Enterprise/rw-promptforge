#!/usr/bin/env python3
"""Side-by-side review of original vs refined soul file.

Usage: python3 compare_soul.py ORIGINAL.md REFINED.md
Prints: size stats, section map, section-level change summary, key diffs.
"""
import re
import sys
import difflib
from pathlib import Path


def section_names(text: str) -> dict[str, int]:
    """Map section name → line number for <name>...</name> style sections."""
    sections = {}
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"<(soul_file|identity|style|protocol|gate|verification|"
                     r"quality_standards|cognitive_framework|infrastructure|"
                     r"process_discipline|memory_system|section_map|header)>", line)
        if m:
            sections[m.group(1)] = i
    return sections


def main():
    orig = Path(sys.argv[1]).read_text()
    refined = Path(sys.argv[2]).read_text()

    o_lines, r_lines = orig.splitlines(), refined.splitlines()

    print(f"{'Metric':<28} {'Original':>12} {'Refined':>12} {'Δ':>10}")
    print("-" * 64)
    for label, a, b in [
        ("Lines", len(o_lines), len(r_lines)),
        ("Chars", len(orig), len(refined)),
    ]:
        delta = b - a
        pct = f"{(b/a-1)*100:+.1f}%" if a else "-"
        print(f"{label:<28} {a:>12,} {b:>12,} {delta:+,} ({pct})")

    print("\nSection presence:")
    o_sec, r_sec = section_names(orig), section_names(refined)
    all_sec = sorted(set(o_sec) | set(r_sec))
    for s in all_sec:
        o = o_sec.get(s, "-")
        r = r_sec.get(s, "-")
        marker = "  " if s in o_sec and s in r_sec else "⚠️"
        print(f"  {marker} {s:<28} orig:line {o:<6} refined:line {r}")

    # Per-section size change for common sections
    print("\nSection size deltas (common sections):")
    for s in sorted(set(o_sec) & set(r_sec)):
        o_start, r_start = o_sec[s], r_sec[s]
        o_end = next((v for k, v in o_sec.items() if v > o_start), len(o_lines))
        r_end = next((v for k, v in r_sec.items() if v > r_start), len(r_lines))
        o_len = o_end - o_start
        r_len = r_end - r_start
        if o_len != r_len:
            print(f"  {s:<28} {o_len:>5} → {r_len:>5} lines ({(r_len-o_len):+,})")

    # Summary of text-level changes via difflib ratio per section
    print("\nSimilarity per section (1.0 = identical):")
    for s in sorted(set(o_sec) & set(r_sec)):
        o_start, r_start = o_sec[s], r_sec[s]
        o_end = next((v for k, v in o_sec.items() if v > o_start), len(o_lines))
        r_end = next((v for k, v in r_sec.items() if v > r_start), len(r_lines))
        o_text = "\n".join(o_lines[o_start - 1 : o_end - 1])
        r_text = "\n".join(r_lines[r_start - 1 : r_end - 1])
        ratio = difflib.SequenceMatcher(None, o_text, r_text).ratio()
        flag = "" if ratio > 0.9 else (" changed" if ratio > 0.6 else " ← REWRITTEN")
        print(f"  {s:<28} {ratio:.3f}{flag}")


if __name__ == "__main__":
    main()
