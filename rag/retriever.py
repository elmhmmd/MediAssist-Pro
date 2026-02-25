from langchain_core.documents import Document
from langchain_ollama import OllamaLLM

from rag.indexer import CHROMA_DIR, load_vectorstore

OLLAMA_MODEL = "mistral"
OLLAMA_BASE_URL = "http://localhost:11434"
RETRIEVAL_K = 10
FINAL_K = 4


def _expand_query(query: str, llm: OllamaLLM) -> list[str]:
    prompt = (
        "Tu es un assistant technique spécialisé dans les équipements biomédicaux de laboratoire. "
        "Génère 2 reformulations concises de la question suivante pour améliorer la recherche documentaire. "
        "Réponds uniquement avec les 2 reformulations, une par ligne, sans numérotation ni explication.\n\n"
        f"Question: {query}"
    )
    response = llm.invoke(prompt)
    expansions = [line.strip() for line in response.strip().split("\n") if line.strip()]
    return [query] + expansions[:2]


def _mmr_rerank(query: str, docs: list[Document], vectorstore, k: int = FINAL_K) -> list[Document]:
    return vectorstore.max_marginal_relevance_search(query, k=k, fetch_k=len(docs))


def retrieve(
    query: str,
    persist_directory: str = CHROMA_DIR,
    k: int = FINAL_K,
    use_query_expansion: bool = True,
    model: str = OLLAMA_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> list[Document]:
    vectorstore = load_vectorstore(persist_directory)
    llm = OllamaLLM(model=model, base_url=base_url)

    queries = _expand_query(query, llm) if use_query_expansion else [query]

    seen_ids = set()
    all_docs = []
    for q in queries:
        for doc in vectorstore.similarity_search(q, k=RETRIEVAL_K):
            doc_id = doc.page_content[:100]
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_docs.append(doc)

    reranked = _mmr_rerank(query, all_docs, vectorstore, k=k)
    return reranked


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Comment entretenir une centrifugeuse?"
    docs = retrieve(query)
    print(f"\nQuery: {query}")
    print(f"Retrieved {len(docs)} chunks:\n")
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        print(f"[{i}] Ch{meta['chapter']} — {meta['chapter_title']} > {meta['section']}")
        print(doc.page_content[:200])
        print()
