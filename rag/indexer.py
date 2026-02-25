import argparse

import chromadb.utils.embedding_functions as chroma_ef
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from rag.pdf_chunker import chunk_text_file

CHROMA_DIR = "chroma_store"


class ChromaDefaultEmbeddings(Embeddings):
    """Wraps ChromaDB's bundled all-MiniLM-L6-v2 (ONNX) as a LangChain Embeddings."""

    def __init__(self):
        self._fn = chroma_ef.DefaultEmbeddingFunction()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._fn(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._fn([text])[0]


def build_vectorstore(
    txt_path: str = "data.txt",
    source: str = "data.pdf",
    persist_directory: str = CHROMA_DIR,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> Chroma:
    embeddings = ChromaDefaultEmbeddings()
    chunks = chunk_text_file(txt_path, source=source, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    print(f"Indexing {len(chunks)} chunks into ChromaDB at '{persist_directory}' ...")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory,
        collection_name="mediassist",
    )
    print("Indexing complete.")
    return vectorstore


def load_vectorstore(persist_directory: str = CHROMA_DIR) -> Chroma:
    return Chroma(
        persist_directory=persist_directory,
        embedding_function=ChromaDefaultEmbeddings(),
        collection_name="mediassist",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build ChromaDB vectorstore from extracted PDF text")
    parser.add_argument("txt_path", nargs="?", default="data.txt")
    parser.add_argument("--source", default="data.pdf")
    parser.add_argument("--persist-dir", default=CHROMA_DIR)
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    args = parser.parse_args()

    build_vectorstore(
        txt_path=args.txt_path,
        source=args.source,
        persist_directory=args.persist_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
