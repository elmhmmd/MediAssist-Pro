import re
from typing import List, Optional, Tuple
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

CHAPTER_PATTERN = re.compile(r"Chapitre\s+(\d+)\s*\n", re.IGNORECASE)

SECTION_PATTERN = re.compile(
    r"^("
    r"PHOTOGRAPHIE|A QUOI SERT|PRINCIPES DE FONCTIONNEMENT|"
    r"CONDITIONS REQUISES|ENTRETIEN DE ROUTINE|GUIDE DE D[EÉ]PANNAGE|"
    r"D[EÉ]FINITIONS|[EÉ]L[EÉ]MENTS DU|CIRCUIT [EÉ]LECTRIQUE|"
    r"FONCTIONNEMENT DU|SCH[EÉ]MA D|COMMANDES DU|"
    r"S[EÉ]CURIT[EÉ] BIOLOGIQUE|UTILISATION DE|"
    r"[EÉ]VALUATION FONCTIONNELLE|RECOMMANDATIONS POUR|ILLUSTRATION|"
    r"[EÉ]talonnage|Entretien courant|Entretien pr[eé]ventif|"
    r"Entretien g[eé]n[eé]ral|Entretien de la balance|"
    r"Maintenance pr[eé]ventive|Maintenance sp[eé]cialis[eé]e|"
    r"Balances m[eé]caniques|Balances [eé]lectroniques|"
    r"Classification des|Types de rotors|D[eé]contamination|"
    r"Certification de|Remplacement de la lampe|"
    r"Fonctionnement du distillateur|Nettoyage du condenseur|"
    r"St[eé]rilisation|Inspection et nettoyage|"
    r"V[eé]rification du fonctionnement|PROC[EÉ]DURE G[EÉ]N[EÉ]RALE|"
    r"Proc[eé]dure g[eé]n[eé]rale|Annexe|ENTRETIEN COURANT DE|"
    r"Nettoyage de l|Autres pr[eé]cautions|Syst[eè]me de traitement|"
    r"Commandes des balances|Utilisation de la balance [eé]lectronique|"
    r"Fonctionnement du bain|Installation$|S[eé]curit[eé]$|"
    r"Utilisation du bain|Entretien$|Nettoyage$|Lubrification|"
    r"Inspection p[eé]riodique|[EÉ]l[eé]ments de la centrifugeuse|"
    r"Tubes$|Rotors$|Outils et instruments|Remplacement du filtre|"
    r"St[eé]rilisation du r[eé]cipient|"
    r"Mat[eé]riel n[eé]cessaire pour les tests ELISA|"
    r"Etapes m[eé]caniques de la technique ELISA|"
    r"Etapes biochimiques de la technique ELISA"
    r")",
    re.MULTILINE | re.IGNORECASE,
)

NOISE_PATTERNS = [
    re.compile(r"MANUEL D[’'.]ENTRETIEN ET DE MAINTENANCE DES APPAREILS DE LABORATOIRE", re.IGNORECASE),
    re.compile(r"^CHAPITRE \d+ [A-Z].*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Photo avec l[’']aimable autorisation[^\n]*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\d{1,3}\s*$", re.MULTILINE),
    re.compile(r"^[•●]\s*[•●]\s*[•●][^\n]*$", re.MULTILINE),
]

CHAPTER_TITLE_FALLBACK = {
    1: "Lecteur de microplaques",
    2: "Laveur de microplaques",
    3: "pH mètre",
    4: "Balances",
    5: "Bains-marie",
    6: "Enceinte de sécurité biologique",
    7: "Centrifugeuses",
    8: "Distillateur",
}


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
    
    min_bucket = min(middle_buckets, key=middle_buckets.get)
    mean_count = sum(buckets.values()) / len(buckets)
    if middle_buckets[min_bucket] >= mean_count * 0.50:
        return None
    
    split_x = min_bucket + bucket_size / 2
    left_count = sum(1 for c in chars if (c["x0"] + c["x1"]) / 2 < split_x)
    right_count = len(chars) - left_count
    if left_count < len(chars) * 0.15 or right_count < len(chars) * 0.15:
        return None
    
    for t in page.find_tables():
        if t.bbox[0] < split_x < t.bbox[2]:
            return None
    
    return split_x


def extract_column_text(page, x0, x1) -> str:
    cropped = page.crop((x0, 0, x1, page.height))
    
    tables = cropped.find_tables()
    table_bboxes = [t.bbox for t in tables]
    table_data = [(t.bbox[1], format_table(t.extract())) for t in tables if t.extract()]
    
    def not_in_table(obj):
        if obj.get("object_type") == "char":
            ox0, otop, ox1, obottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
            for bbox in table_bboxes:
                if ox0 >= bbox[0] - 3 and ox1 <= bbox[2] + 3 and otop >= bbox[1] - 3 and obottom <= bbox[3] + 3:
                    return False
        return True
    
    non_table = cropped.filter(not_in_table)
    
    lines_by_y = {}
    for char in non_table.chars:
        y_key = round(char["top"] / 5) * 5
        if y_key not in lines_by_y:
            lines_by_y[y_key] = []
        lines_by_y[y_key].append(char)
    
    text_blocks = []
    for y in sorted(lines_by_y.keys()):
        chars = sorted(lines_by_y[y], key=lambda c: c["x0"])
        line = "".join(c["text"] for c in chars)
        text_blocks.append((y, line.strip()))
    
    for y, table_text in table_data:
        text_blocks.append((y, "\n" + table_text))
    
    text_blocks.sort(key=lambda x: x[0])
    
    lines = []
    prev_y = None
    for y, text in text_blocks:
        if prev_y is not None and y - prev_y > 20:
            lines.append("")
        lines.append(text)
        prev_y = y
    
    return "\n".join(lines)


def extract_column_lines(page, x0, x1) -> List[Tuple[float, str]]:
    cropped = page.crop((x0, 0, x1, page.height))
    
    tables = cropped.find_tables()
    table_bboxes = [t.bbox for t in tables]
    table_data = [(t.bbox[1], format_table(t.extract())) for t in tables if t.extract()]
    
    def not_in_table(obj):
        if obj.get("object_type") == "char":
            ox0, otop, ox1, obottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
            for bbox in table_bboxes:
                if ox0 >= bbox[0] - 3 and ox1 <= bbox[2] + 3 and otop >= bbox[1] - 3 and obottom <= bbox[3] + 3:
                    return False
        return True
    
    non_table = cropped.filter(not_in_table)
    
    lines_by_y = {}
    for char in non_table.chars:
        y_key = round(char["top"] / 5) * 5
        if y_key not in lines_by_y:
            lines_by_y[y_key] = []
        lines_by_y[y_key].append(char)
    
    blocks = []
    for y in sorted(lines_by_y.keys()):
        chars = sorted(lines_by_y[y], key=lambda c: c["x0"])
        line = "".join(c["text"] for c in chars)
        if line.strip():
            blocks.append((y, line.strip()))
    
    for y, table_text in table_data:
        blocks.append((y, table_text))
    
    blocks.sort(key=lambda x: x[0])
    return blocks


def extract_page_text(page) -> str:
    def filter_objs(obj):
        if obj.get("object_type") == "char":
            if not obj.get("upright", True):
                return False
            if obj["top"] < 70 or obj["bottom"] > page.height - 60:
                return False
        return True
    
    p = page.filter(filter_objs)
    
    split_x = find_column_split(p)
    
    if not split_x:
        lines = extract_column_lines(p, 0, page.width)
        return "\n".join(text for _, text in lines)
    
    chars = p.chars
    lines_by_y = {}
    for c in chars:
        y_key = round(c["top"] / 5) * 5
        if y_key not in lines_by_y:
            lines_by_y[y_key] = []
        lines_by_y[y_key].append(c)
    
    true_full_width = []
    column_y_ranges = []
    
    for y in list(lines_by_y.keys()):
        line_chars = lines_by_y[y]
        min_x = min(c["x0"] for c in line_chars)
        max_x = max(c["x1"] for c in line_chars)
        
        if min_x < split_x - 30 and max_x > split_x + 30:
            left_chars = [c for c in line_chars if (c["x0"] + c["x1"]) / 2 < split_x]
            right_chars = [c for c in line_chars if (c["x0"] + c["x1"]) / 2 >= split_x]
            
            left_max_x = max(c["x1"] for c in left_chars) if left_chars else 0
            right_min_x = min(c["x0"] for c in right_chars) if right_chars else 0
            gap = right_min_x - left_max_x
            
            if gap < 15:
                text = "".join(c["text"] for c in sorted(line_chars, key=lambda c: c["x0"]))
                if text.strip():
                    true_full_width.append((y, text.strip()))
                    column_y_ranges.append((y - 8, y + 18))
    
    def not_full_width(obj):
        if obj.get("object_type") == "char":
            y = obj["top"]
            for y0, y1 in column_y_ranges:
                if y0 <= y <= y1:
                    return False
        return True
    
    remaining = p.filter(not_full_width)
    
    left_lines = extract_column_lines(remaining, 0, split_x)
    right_lines = extract_column_lines(remaining, split_x, page.width)
    
    left_text = "\n".join(text for _, text in left_lines)
    right_text = "\n".join(text for _, text in right_lines)
    
    all_blocks = []
    for y, text in left_lines:
        all_blocks.append((y, text, "left"))
    for y, text in true_full_width:
        all_blocks.append((y, text, "full"))
    
    all_blocks.sort(key=lambda x: x[0])
    
    left_and_full = "\n".join(text for _, text, _ in all_blocks)
    
    parts = [p for p in [left_and_full, right_text] if p.strip()]
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
    text = "\n".join(dedupe_line(l) for l in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_pdf(pdf_path: str) -> Tuple[str, str]:
    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [extract_page_text(p) for p in pdf.pages]
    full_text = clean_text("\n".join(pages_text))
    print(f"Loaded {len(pages_text)} pages from {pdf_path}")
    return full_text, pdf_path


def split_into_chapters(text: str) -> List[Tuple[int, str, str]]:
    matches = list(CHAPTER_PATTERN.finditer(text))
    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((int(match.group(1)), CHAPTER_TITLE_FALLBACK.get(int(match.group(1)), ""), text[start:end]))
    print(f"Found {len(chapters)} chapters")
    return chapters


def extract_section_candidate(line: str) -> str:
    line = line.strip(" |")
    m = re.match(r"^([A-ZÉÈÀÙÂÊÎÔÛÇŒ][A-ZÉÈÀÙÂÊÎÔÛÇŒ \-']{4,})(?:\s+[a-z0-9].*)?$", line)
    if m:
        return m.group(1).strip()
    return line


def split_into_sections(chapter_text: str) -> List[Tuple[str, str]]:
    lines = chapter_text.split("\n")
    sections = []
    current_title = "INTRODUCTION"
    current_lines = []

    for line in lines:
        raw = " ".join(line.strip().split())
        if not raw:
            continue
        candidate = extract_section_candidate(raw)
        if SECTION_PATTERN.match(candidate):
            content = "\n".join(current_lines).strip()
            if content:
                sections.append((current_title, content))
            current_title = candidate
            current_lines = []
        else:
            current_lines.append(raw)

    content = "\n".join(current_lines).strip()
    if content:
        sections.append((current_title, content))

    return sections


def chunk_section(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    ).split_text(text)


def process(pdf_path: str, chunk_size: int = 800, chunk_overlap: int = 150) -> List[Document]:
    full_text, source = load_pdf(pdf_path)
    chapters = split_into_chapters(full_text)
    chunks = []

    for chapter_num, chapter_title, chapter_text in chapters:
        for section_title, section_text in split_into_sections(chapter_text):
            for i, chunk_text in enumerate(chunk_section(section_text, chunk_size, chunk_overlap)):
                chunks.append(Document(
                    page_content=chunk_text,
                    metadata={
                        "source": source,
                        "chapter": chapter_num,
                        "chapter_title": chapter_title,
                        "section": section_title,
                        "chunk_index": len(chunks),
                        "sub_chunk": i,
                    },
                ))

    print(f"Total chunks: {len(chunks)}")
    return chunks


if __name__ == "__main__":
    chunks = process("data.pdf")

    print("\n--- Ch1 sections preview ---")
    seen = set()
    for c in chunks:
        if c.metadata["chapter"] == 1:
            key = c.metadata["section"]
            if key not in seen:
                seen.add(key)
                print(f"\n[{key}]")
                print(c.page_content)