import mlflow
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import OllamaLLM

from rag.indexer import CHROMA_DIR
from rag.mlflow_logger import (
    log_llm_config,
    log_query_response,
    log_rag_config,
    setup_mlflow,
)
from rag.retriever import OLLAMA_BASE_URL, OLLAMA_MODEL, retrieve

SYSTEM_PROMPT = (
    "Tu es un assistant technique expert en équipements biomédicaux de laboratoire. "
    "Tu réponds aux questions des techniciens de laboratoire de façon précise, claire et actionnable. "
    "Tes réponses sont basées uniquement sur le contexte fourni. "
    "Si l'information n'est pas dans le contexte, dis-le explicitement. "
    "Cite toujours le chapitre et la section source de tes informations."
)

PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", (
        "Contexte extrait du manuel technique:\n\n{context}\n\n"
        "Question: {question}\n\n"
        "Réponds en français de façon précise et structurée."
    )),
])


def _format_context(docs: list[Document]) -> str:
    parts = []
    for doc in docs:
        meta = doc.metadata
        header = f"[Chapitre {meta['chapter']} — {meta['chapter_title']} > {meta['section']}]"
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def build_rag_chain(
    persist_directory: str = CHROMA_DIR,
    model: str = OLLAMA_MODEL,
    base_url: str = OLLAMA_BASE_URL,
):
    llm = OllamaLLM(model=model, base_url=base_url, temperature=0.1, top_p=0.9)

    def retrieve_and_format(inputs: dict) -> dict:
        docs = retrieve(
            inputs["question"],
            persist_directory=persist_directory,
            model=model,
            base_url=base_url,
        )
        return {
            "context": _format_context(docs),
            "question": inputs["question"],
        }

    chain = (
        RunnablePassthrough()
        | retrieve_and_format
        | (lambda x: {"context": x["context"], "question": x["question"]})
        | PROMPT_TEMPLATE
        | llm
        | StrOutputParser()
    )
    return chain


def ask(
    question: str,
    persist_directory: str = CHROMA_DIR,
    model: str = OLLAMA_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    log: bool = True,
) -> str:
    setup_mlflow()
    chain = build_rag_chain(persist_directory, model, base_url)

    with mlflow.start_run():
        log_rag_config()
        log_llm_config(model=model, prompt_template=SYSTEM_PROMPT)

        docs = retrieve(question, persist_directory=persist_directory, model=model, base_url=base_url)
        context = _format_context(docs)
        answer = chain.invoke({"question": question})

        if log:
            log_query_response(question=question, answer=answer, context=context)

    return answer


if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Comment entretenir une centrifugeuse?"
    print(f"Question: {question}\n")
    answer = ask(question)
    print(f"Réponse:\n{answer}")
