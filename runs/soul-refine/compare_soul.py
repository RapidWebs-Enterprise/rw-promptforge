#!/usr/bin/env python3
"""Side-by-side review of original vs refined soul file (tag-aware).

Usage: python3 compare_soul.py ORIGINAL.md REFINED.md [--diff]
Prints: size stats, section presence, per-section size deltas, similarity
ratios, and (with --diff) a unified diff per changed section.
"""
import re
import sys
import difflib
from pathlib import Path

SECTION_TAGS = [
    "soul_file", "header", "section_map", "identity", "style", "protocol",
    "gate", "verification", "quality_standards", "cognitive_framework",
    "infrastructure", "process_discipline", "memory_system",
]

# Match ANY tag carrying name="x" — tag format varies (protocol/gate/verification...)
SECTION_RE = re.compile(r'<([a-z_]+) name="([a-z_]+)"')


def sections(text: str) -> dict[str, tuple[int, int, str, str]]:
    """Map section name → (start_line, end_line, tag, content).

    Sections are found by scanning for any <tag name="x"> opener; content
    spans from the opener's line to the line before the next section.
    """
    lines = text.splitlines()
    found: list[tuple[int, str, str]] = []  # (line_idx, tag, name)
    for i, line in enumerate(lines):
        for m in SECTION_RE.finditer(line):
            found.append((i, m.group(1), m.group(2)))
    result: dict[str, tuple[int, int, str, str]] = {}
    for j, (start, tag, name) in enumerate(found):
        end = found[j + 1][0] if j + 1 < len(found) else len(lines)
        content = "\n".join(lines[start:end])
        result[name] = (start + 1, end, tag, content)
    return result


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_diff = "--diff" in sys.argv
    if len(args) < 2:
        print("Usage: compare_soul.py ORIGINAL.md REFINED.md [--diff]")
        sys.exit(1)

    orig = Path(args[0]).read_text()
    refined = Path(args[1]).read_text()
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

    o_sec, r_sec = sections(orig), sections(refined)

    print("\nSection presence:")
    all_sec = sorted(set(o_sec) | set(r_sec))
    for s in all_sec:
        o = o_sec.get(s)
        r = r_sec.get(s)
        tag_o = o[2] if o else "-"
        tag_r = r[2] if r else "-"
        status = "OK" if o and r else ("ADDED" if r else "DELETED")
        print(f"  [{status:<6}] {s:<28} {tag_o:>14} → {tag_r:<14} lines {o[0] if o else '-':<6} → {r[0] if r else '-'}")

    print("\nSection size deltas (common sections):")
    for s in sorted(set(o_sec) & set(r_sec)):
        o_start, o_end, _, _ = o_sec[s]
        r_start, r_end, _, _ = r_sec[s]
        o_len = o_end - o_start
        r_len = r_end - r_start
        if o_len != r_len:
            print(f"  {s:<28} {o_len:>5} → {r_len:>5} lines ({(r_len-o_len):+,})")

    print("\nSimilarity per section (1.0 = identical):")
    for s in sorted(set(o_sec) & set(r_sec)):
        o_text = o_sec[s][3]
        r_text = r_sec[s][3]
        ratio = difflib.SequenceMatcher(None, o_text, r_text).ratio()
        flag = "" if ratio > 0.9 else (" changed" if ratio > 0.6 else " ← REWRITTEN")
        print(f"  {s:<28} {ratio:.3f}{flag}")

    if show_diff:
        print("\n" + "=" * 72)
        print("UNIFIED DIFF (changed sections only)")
        print("=" * 72)
        for s in sorted(set(o_sec) & set(r_sec)):
            o_text = o_sec[s][3].splitlines()
            r_text = r_sec[s][3].splitlines()
            if o_text == r_text:
                continue
            print(f"\n--- [{o_sec[s][2]} name=\"{s}\"] (orig lines {o_sec[s][0]}-{o_sec[s][1]})")
            print(f"+++ [{r_sec[s][2]} name=\"{s}\"] (refined lines {r_sec[s][0]}-{r_sec[s][1]})")
            diff = difflib.unified_diff(o_text, r_text, lineterm="", n=1)
            for line in diff:
                if line.startswith(("---", "+++")):
                    continue
                print(f"  {line}")


if __name__ == "__main__":
    main()
