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
    r"St[eé]rilisation du r[eé]cipient"
    r")",
    re.MULTILINE,
)

NOISE_PATTERNS = [
    re.compile(r"MANUEL D.ENTRETIEN ET DE MAINTENANCE DES APPAREILS DE LABORATOIRE"),
    re.compile(r"CHAPITRE \d+\s+\S[^\n]*"),
    re.compile(r"^Photo avec l.aimable autorisation[^\n]*$", re.MULTILINE),
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
        rows.append(" | ".join(str(c).strip() if c else "" for c in row))
    return "\n".join(rows)


def extract_col(col) -> str:
    tables = col.find_tables()
    table_bboxes = [t.bbox for t in tables]
    table_texts = [format_table(t.extract()) for t in tables if t.extract()]

    if table_bboxes:
        non_table_text = col.filter(
            lambda obj: obj["object_type"] == "char"
            and not any(
                obj["x0"] >= bbox[0] - 2
                and obj["x1"] <= bbox[2] + 2
                and obj["top"] >= bbox[1] - 2
                and obj["bottom"] <= bbox[3] + 2
                for bbox in table_bboxes
            )
        ).extract_text() or ""
    else:
        non_table_text = col.extract_text() or ""

    return "\n".join(p for p in [non_table_text] + table_texts if p.strip())


def find_column_split(page) -> Optional[float]:
    chars = page.chars
    if not chars:
        return None

    page_width = page.width
    bucket_size = 20
    buckets: dict = {}
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


def extract_page_text(page) -> str:
    split_x = find_column_split(page)
    if split_x:
        left_text = extract_col(page.crop((0, 0, split_x, page.height)))
        right_text = extract_col(page.crop((split_x, 0, page.width, page.height)))
        return "\n".join(p for p in [left_text, right_text] if p.strip())
    return extract_col(page)


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
