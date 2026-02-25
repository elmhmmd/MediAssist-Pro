import re
import statistics
from pathlib import Path
from typing import List, Optional, Tuple

import pdfplumber

NOISE_PATTERNS = [
    re.compile(r"^(?:M?ANUEL|NUEL)\s+D[’'.]?\s*ENTRETIEN[^\n]*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^CHAPITRE \d+ [A-Z].*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Photo avec l[’']aimable autorisation[^\n]*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\d{1,3}\s*$", re.MULTILINE),
    re.compile(r"^[•●]\s*[•●]\s*[•●][^\n]*$", re.MULTILINE),
]


def format_table(table: List[List]) -> str:
    rows = []
    for row in table:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        cleaned_row = [str(c).replace("\n", " ").strip() if c else "" for c in row]
        rows.append(" | ".join(cleaned_row))
    return "\n".join(rows)


def find_column_split(page) -> Optional[float]:
    chars = page.chars
    if not chars:
        return None

    page_width = page.width
    bucket_size = 20
    buckets = {}
    for c in chars:
        x = (c["x0"] + c["x1"]) / 2
        b = int(x // bucket_size) * bucket_size
        buckets[b] = buckets.get(b, 0) + 1

    search_left = page_width * 0.25
    search_right = page_width * 0.75
    middle_buckets = {b: v for b, v in buckets.items() if search_left <= b <= search_right}
    if not middle_buckets:
        return None

    def split_is_balanced(split_x: float) -> bool:
        left_count = sum(1 for c in chars if (c["x0"] + c["x1"]) / 2 < split_x)
        right_count = len(chars) - left_count
        return left_count >= len(chars) * 0.15 and right_count >= len(chars) * 0.15

    def column_gap_score(split_x: float) -> Tuple[int, int]:
        lines_by_y = {}
        for c in chars:
            y_key = round(c["top"] / 5) * 5
            lines_by_y.setdefault(y_key, []).append(c)

        dual_gap_lines = 0
        bridge_lines = 0
        for line_chars in lines_by_y.values():
            left = [c for c in line_chars if (c["x0"] + c["x1"]) / 2 < split_x]
            right = [c for c in line_chars if (c["x0"] + c["x1"]) / 2 >= split_x]
            if not left or not right:
                continue
            gap = min(c["x0"] for c in right) - max(c["x1"] for c in left)
            if gap > 20:
                dual_gap_lines += 1
            elif gap < 8:
                bridge_lines += 1
        return dual_gap_lines, bridge_lines

    min_bucket = min(middle_buckets, key=middle_buckets.get)
    mean_count = sum(buckets.values()) / len(buckets)
    split_x = min_bucket + bucket_size / 2
    if middle_buckets[min_bucket] < mean_count * 0.65 and split_is_balanced(split_x):
        return split_x

    fallback_split = page_width / 2
    if split_is_balanced(fallback_split):
        dual_gap_lines, bridge_lines = column_gap_score(fallback_split)
        if dual_gap_lines >= 10 and dual_gap_lines >= bridge_lines:
            return fallback_split

    return None


def extract_column_lines(page, x0, x1) -> List[Tuple[float, str, float]]:
    tables = [t for t in page.find_tables() if x0 <= ((t.bbox[0] + t.bbox[2]) / 2) < x1]
    table_bboxes = [t.bbox for t in tables]
    table_data = [(t.bbox[1], format_table(t.extract())) for t in tables if t.extract()]

    def is_in_table(char) -> bool:
        ox0, otop, ox1, obottom = char["x0"], char["top"], char["x1"], char["bottom"]
        for bbox in table_bboxes:
            if ox0 >= bbox[0] - 3 and ox1 <= bbox[2] + 3 and otop >= bbox[1] - 3 and obottom <= bbox[3] + 3:
                return True
        return False

    lines_by_y = {}
    for char in page.chars:
        mid_x = (char["x0"] + char["x1"]) / 2
        if mid_x < x0 or mid_x >= x1:
            continue
        if is_in_table(char):
            continue
        y_key = round(char["top"] / 5) * 5
        if y_key not in lines_by_y:
            lines_by_y[y_key] = []
        lines_by_y[y_key].append(char)

    blocks = []
    for y in sorted(lines_by_y.keys()):
        chars = sorted(lines_by_y[y], key=lambda c: c["x0"])
        line = "".join(c["text"] for c in chars)
        if line.strip():
            blocks.append((y, line.strip(), statistics.median(c["size"] for c in chars)))

    for y, table_text in table_data:
        blocks.append((y, table_text, 10.0))

    blocks.sort(key=lambda x: x[0])
    return blocks


POST_FIGURE_BOUNDARY_RE = re.compile(
    r"^(Etapes|Étapes|Procédure|Etalonnage|Étalonnage|CONDITIONS|ENTRETIEN|GUIDE|DÉFINITIONS|"
    r"A QUOI|PRINCIPES|Annexe|Chapitre)\b",
    re.IGNORECASE,
)

ALLOWED_SINGLE_WORD_LINES = {
    "DÉFINITIONS",
    "Annexe",
    "Balances",
    "Bains-marie",
    "Centrifugeuses",
    "Distillateur",
    "Entretien",
    "Nettoyage",
    "Tubes",
}


def _normalize_line(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip()


def _lower_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.islower()) / len(letters)


def _is_boundary_after_figure(line: str) -> bool:
    words = line.split()
    if POST_FIGURE_BOUNDARY_RE.match(line):
        return True
    if line.startswith(("••", "•", "-", "–")) or re.match(r"^\d+\.", line):
        return True
    if len(words) >= 7 and (line.endswith((".", ":", ";", "?", "!")) or _lower_ratio(line) > 0.55):
        return True
    return False


def sanitize_extracted_lines(lines: List[Tuple[str, float]]) -> List[str]:
    cleaned = []
    in_figure_block = False

    for raw_line, size in lines:
        original = raw_line.strip()
        line = _normalize_line(raw_line)
        line = re.sub(r"\b([A-Za-zÀ-ÿ]{4,})\d{1,2}$", r"\1", line)
        line = re.sub(r"\b([a-zà-ÿ])\1([a-zà-ÿ]{3,})\b", r"\1\2", line)

        if not line:
            if not in_figure_block and cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue

        if size < 8.3:
            continue
        if re.match(r"^\d{1,3}$", line):
            continue
        if re.match(r"^[A-Za-zÀ-ÿ]{1,2}$", line):
            continue
        if re.match(r"^(?:M?ANUEL|NUEL)\b", line, re.IGNORECASE):
            continue
        if line == "••":
            continue
        if len(line.split()) == 1 and line not in ALLOWED_SINGLE_WORD_LINES:
            continue

        if re.match(r"^Figure\s+\d+\.", line, re.IGNORECASE):
            trailing = None
            tail_match = re.match(r"^Figure\s+\d+\.[^\n]*?\s{2,}(.+)$", original, re.IGNORECASE)
            if tail_match:
                trailing = _normalize_line(tail_match.group(1))
            in_figure_block = True
            if trailing and _is_boundary_after_figure(trailing):
                in_figure_block = False
                cleaned.append(trailing)
            continue

        if in_figure_block:
            if _is_boundary_after_figure(line):
                in_figure_block = False
            else:
                continue

        cleaned.append(line)

    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return cleaned


def extract_page_text(page) -> str:
    def filter_objs(obj):
        if obj.get("object_type") == "char":
            if not obj.get("upright", True):
                return False
            if obj["top"] < 130 or obj["bottom"] > page.height - 60:
                return False
        return True

    p = page.filter(filter_objs)
    split_x = find_column_split(p)

    if not split_x:
        lines = extract_column_lines(p, 0, page.width)
        return "\n".join(sanitize_extracted_lines([(text, size) for _, text, size in lines]))

    # Keep a narrow gutter around the split and bias boundary chars to the right column.
    gutter = 6
    left_lines = extract_column_lines(p, 0, max(split_x - gutter, 0))
    right_lines = extract_column_lines(p, max(split_x - gutter, 0), page.width)

    # Rejoin lines where the split cuts a short lowercase word in two parts.
    used_left = set()
    used_right = set()
    merged_lines = []
    right_by_y = {}
    for i, (y, text, size) in enumerate(right_lines):
        right_by_y.setdefault(y, []).append((i, text, size))

    for i, (y, left_text, left_size) in enumerate(left_lines):
        for j, right_text, right_size in right_by_y.get(y, []):
            if j in used_right:
                continue
            left_part = left_text.rstrip()
            right_part = right_text.lstrip()
            merged = f"{left_part}{right_part}".strip()
            left_tokens = left_part.split()
            left_tail = left_tokens[-1] if left_tokens else ""
            if (
                left_part
                and right_part
                and len(merged) <= 60
                and " " not in right_part
                and right_part.isalpha()
                and left_tail.isalpha()
                and right_part.islower()
                and left_tail.islower()
                and len(right_part) <= 12
                and len(left_tail) <= 12
            ):
                merged_lines.append((y, merged, max(left_size, right_size)))
                used_left.add(i)
                used_right.add(j)
                break

    left_blocks = [(y, text, size) for i, (y, text, size) in enumerate(left_lines) if i not in used_left]
    left_blocks.extend(merged_lines)
    left_blocks.sort(key=lambda x: x[0])

    left_text = "\n".join(sanitize_extracted_lines([(text, size) for _, text, size in left_blocks]))
    right_text = "\n".join(
        sanitize_extracted_lines([(text, size) for i, (_, text, size) in enumerate(right_lines) if i not in used_right])
    )

    parts = [part for part in [left_text, right_text] if part.strip()]
    return "\n\n".join(parts)


def dedupe_line(line: str) -> str:
    stripped = line.replace(" ", "")
    if len(stripped) < 6:
        return line
    pairs = sum(1 for i in range(0, len(stripped) - 1, 2) if stripped[i] == stripped[i + 1])
    if pairs >= len(stripped) / 2 * 0.75:
        return re.sub(r"(.)\1", r"\1", line)
    return line


def clean_text(text: str) -> str:
    for pattern in NOISE_PATTERNS:
        text = pattern.sub("", text)
    text = "\n".join(dedupe_line(line) for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_pdf_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [extract_page_text(page) for page in pdf.pages]
    print(f"Loaded {len(pages_text)} pages from {pdf_path}")
    return clean_text("\n".join(pages_text))


def extract_pdf_to_txt(pdf_path: str, txt_path: Optional[str] = None) -> str:
    output_path = Path(txt_path) if txt_path else Path(pdf_path).with_suffix(".txt")
    text = extract_pdf_text(pdf_path)
    output_path.write_text(text, encoding="utf-8")
    print(f"Saved extracted text to {output_path}")
    return str(output_path)


if __name__ == "__main__":
    import sys

    pdf = sys.argv[1] if len(sys.argv) > 1 else "data.pdf"
    txt = sys.argv[2] if len(sys.argv) > 2 else None
    extract_pdf_to_txt(pdf, txt)
