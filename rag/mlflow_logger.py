import mlflow
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from langchain_ollama import OllamaLLM

from rag.retriever import FINAL_K, OLLAMA_BASE_URL, OLLAMA_MODEL

MLFLOW_EXPERIMENT = "mediassist-rag"


class OllamaEvalLLM(DeepEvalBaseLLM):
    """Wraps Ollama so DeepEval can use it for metric evaluation."""

    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        self._llm = OllamaLLM(model=model, base_url=base_url)

    def load_model(self):
        return self._llm

    def generate(self, prompt: str) -> str:
        return self._llm.invoke(prompt)

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return f"ollama/{OLLAMA_MODEL}"


def setup_mlflow(tracking_uri: str = "mlruns"):
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)


def log_rag_config(
    chunk_size: int = 800,
    chunk_overlap: int = 150,
    chunking_strategy: str = "recursive_character",
    embed_model: str = "all-MiniLM-L6-v2",
    embed_dimensions: int = 384,
    normalize_embeddings: bool = True,
    similarity_metric: str = "cosine",
    retrieval_k: int = FINAL_K,
    reranking: str = "MMR",
):
    mlflow.log_params({
        "chunking.chunk_size": chunk_size,
        "chunking.chunk_overlap": chunk_overlap,
        "chunking.strategy": chunking_strategy,
        "embedding.model": embed_model,
        "embedding.dimensions": embed_dimensions,
        "embedding.normalize": normalize_embeddings,
        "retrieval.similarity_metric": similarity_metric,
        "retrieval.k": retrieval_k,
        "retrieval.reranking": reranking,
    })


def log_llm_config(
    model: str = OLLAMA_MODEL,
    temperature: float = 0.1,
    top_p: float = 0.9,
    top_k: int = 40,
    max_tokens: int = 2048,
    prompt_template: str = "",
):
    mlflow.log_params({
        "llm.model": model,
        "llm.temperature": temperature,
        "llm.top_p": top_p,
        "llm.top_k": top_k,
        "llm.max_tokens": max_tokens,
        "llm.prompt_template": prompt_template[:500],
    })


def log_query_response(
    question: str,
    answer: str,
    context: str,
    run_id: str | None = None,
    evaluate: bool = True,
):
    with mlflow.start_run(run_id=run_id, nested=True):
        mlflow.log_param("question", question[:500])
        mlflow.log_text(answer, "response.txt")
        mlflow.log_text(context, "context.txt")

        if evaluate:
            try:
                eval_llm = OllamaEvalLLM()
                test_case = LLMTestCase(
                    input=question,
                    actual_output=answer,
                    retrieval_context=[context],
                )
                relevancy = AnswerRelevancyMetric(model=eval_llm, threshold=0.5)
                faithfulness = FaithfulnessMetric(model=eval_llm, threshold=0.5)
                relevancy.measure(test_case)
                faithfulness.measure(test_case)
                mlflow.log_metrics({
                    "rag.answer_relevancy": relevancy.score,
                    "rag.faithfulness": faithfulness.score,
                })
            except Exception as e:
                mlflow.log_param("eval_error", str(e)[:200])
