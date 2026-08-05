"""Merge good sections from refined SOUL.md into original, keeping everything else intact."""

from pathlib import Path
import re

orig = Path('runs/soul-refine/ORIGINAL_SAVED.md').read_text()
real = Path('runs/soul-refine/REFINED_REAL.md').read_text()

# All known section tags
SECTION_TAGS = ('section','protocol','gate','verification','quality_standards',
    'cognitive_framework','infrastructure','process_discipline','identity','style',
    'memory_system','header','section_map','soul_file')

def get_section(text, name):
    """Extract a section by name, returning (tag, full_opening_tag, content)."""
    for tag in SECTION_TAGS:
        pattern = '<' + tag + ' name="' + name + '"'
        m = re.search(pattern, text)
        if m:
            start = m.start()
            open_end = text.find('>', start) + 1
            opening = text[start:open_end]
            close_tag = '</' + tag + '>'
            close_pos = text.find(close_tag, open_end)
            if close_pos != -1:
                content = text[open_end:close_pos]
                return tag, opening, content
    return None, None, None

def replace_section(text, name, new_content):
    """Replace section content in text, preserving opening tag with all attributes."""
    tag, opening, _ = get_section(text, name)
    if not tag:
        print('  WARNING: section ' + name + ' not found, skipping')
        return text
    close_tag = '</' + tag + '>'
    # Find the section in text
    esc_opening = re.escape(opening)
    esc_close = re.escape(close_tag)
    pattern = esc_opening + r'.*?' + esc_close
    replacement = opening + new_content + close_tag
    result = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
    if result == text:
        print('  WARNING: replacement failed for ' + name)
    return result

# Sections to take FROM REFINED (keep original for everything else)
replacements = [
    'session_protocol',
    'reflexion_gate', 
    'anti_hallucination',
    'modern_prompting',
    'session_state_trust',
]

merged = orig

for name in replacements:
    _, _, content = get_section(real, name)
    if content:
        merged = replace_section(merged, name, content)
        print('  Replaced: ' + name)
    else:
        print('  Skipped: ' + name + ' (no content in refined)')

# Save
output = Path('runs/soul-refine/MERGED_SOUL.md')
output.write_text(merged)
print()
print('Saved to: ' + str(output))
print('Original: ' + str(len(orig)) + ' chars  ' + str(len(orig.splitlines())) + ' lines')
print('Merged:   ' + str(len(merged)) + ' chars  ' + str(len(merged.splitlines())) + ' lines')