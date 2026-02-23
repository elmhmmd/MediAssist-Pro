import re
from pathlib import Path
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from rag.pdf_extractor import extract_pdf_to_txt
except ImportError:
    from pdf_extractor import extract_pdf_to_txt

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


def load_text_source(pdf_path: str, txt_path: Optional[str] = None) -> Tuple[str, str]:
    output_path = extract_pdf_to_txt(pdf_path, txt_path)
    full_text = Path(output_path).read_text(encoding="utf-8")
    return full_text, pdf_path


def split_into_chapters(text: str) -> List[Tuple[int, str, str]]:
    matches = list(CHAPTER_PATTERN.finditer(text))
    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapter_num = int(match.group(1))
        chapters.append((chapter_num, CHAPTER_TITLE_FALLBACK.get(chapter_num, ""), text[start:end]))
    print(f"Found {len(chapters)} chapters")
    return chapters


def extract_section_candidate(line: str) -> str:
    line = line.strip(" |")
    m = re.match(r"^([A-ZÉÈÀÙÂÊÎÔÛÇŒ][A-ZÉÈÀÙÂÊÎÔÛÇŒ \-']{4,})(?:\s+[a-z0-9].*)?$", line)
    if m:
        line = m.group(1).strip()
    return re.sub(r"\d{1,2}$", "", line).strip()


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
        section_match = SECTION_PATTERN.match(candidate)
        if section_match:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append((current_title, content))

            matched_title = section_match.group(0).strip()
            if (
                len(candidate) - len(matched_title) > 35
                or "Figure " in candidate
                or re.search(r"\d+\.\s", candidate)
            ):
                current_title = matched_title
            else:
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


def process(
    pdf_path: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
    txt_path: Optional[str] = None,
) -> List[Document]:
    full_text, source = load_text_source(pdf_path, txt_path)
    chapters = split_into_chapters(full_text)
    chunks = []

    for chapter_num, chapter_title, chapter_text in chapters:
        for section_title, section_text in split_into_sections(chapter_text):
            for i, chunk_text in enumerate(chunk_section(section_text, chunk_size, chunk_overlap)):
                chunks.append(
                    Document(
                        page_content=chunk_text,
                        metadata={
                            "source": source,
                            "chapter": chapter_num,
                            "chapter_title": chapter_title,
                            "section": section_title,
                            "chunk_index": len(chunks),
                            "sub_chunk": i,
                        },
                    )
                )

    print(f"Total chunks: {len(chunks)}")
    return chunks


if __name__ == "__main__":
    chunks = process("data.pdf", txt_path="data.txt")

    print("\n--- Ch1 sections preview ---")
    seen = set()
    for c in chunks:
        if c.metadata["chapter"] == 1:
            key = c.metadata["section"]
            if key not in seen:
                seen.add(key)
                print(f"\n[{key}]")
                print(c.page_content)
