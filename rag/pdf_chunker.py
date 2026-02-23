import argparse
from pathlib import Path
from typing import List

from langchain_core.documents import Document

from pdf_processor import chunk_section, split_into_chapters, split_into_sections


def chunk_text_file(
    txt_path: str,
    source: str = "data.pdf",
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[Document]:
    text = Path(txt_path).read_text(encoding="utf-8")
    chapters = split_into_chapters(text)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk extracted PDF text")
    parser.add_argument("txt_path", nargs="?", default="data.txt")
    parser.add_argument("--source", default="data.pdf")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    args = parser.parse_args()

    chunks = chunk_text_file(
        txt_path=args.txt_path,
        source=args.source,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print("\n--- Ch1 sections preview ---")
    seen = set()
    for chunk in chunks:
        if chunk.metadata["chapter"] != 1:
            continue
        section = chunk.metadata["section"]
        if section in seen:
            continue
        seen.add(section)
        print(f"\n[{section}]")
        print(chunk.page_content)


if __name__ == "__main__":
    main()
