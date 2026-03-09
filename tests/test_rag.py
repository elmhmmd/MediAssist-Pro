from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from rag.pdf_chunker import chunk_text_file
from rag.pdf_extractor import extract_pdf_text


def test_chunk_text_file(tmp_path):
    txt = tmp_path / "sample.txt"
    txt.write_text(
        "Chapitre 1\nLecteur de microplaques\n\nA QUOI SERT\nCe lecteur sert à mesurer l'absorbance.\n"
        "Il est utilisé dans les laboratoires d'analyses médicales.\n",
        encoding="utf-8",
    )
    chunks = chunk_text_file(str(txt), source="test.pdf")
    assert len(chunks) > 0
    for chunk in chunks:
        assert "source" in chunk.metadata
        assert "chapter" in chunk.metadata
        assert "section" in chunk.metadata
        assert chunk.page_content.strip() != ""


def test_chunk_metadata_fields(tmp_path):
    txt = tmp_path / "sample.txt"
    txt.write_text(
        "Chapitre 2\nLaveur de microplaques\n\nENTRETIEN DE ROUTINE\nNettoyez les buses régulièrement.\n",
        encoding="utf-8",
    )
    chunks = chunk_text_file(str(txt), source="test.pdf")
    assert len(chunks) > 0
    meta = chunks[0].metadata
    assert meta["chapter"] == 2
    assert meta["source"] == "test.pdf"
    assert "chunk_index" in meta
    assert "sub_chunk" in meta


@patch("rag.rag_pipeline.mlflow")
@patch("rag.rag_pipeline.log_query_response")
@patch("rag.rag_pipeline.log_llm_config")
@patch("rag.rag_pipeline.log_rag_config")
@patch("rag.rag_pipeline.retrieve")
@patch("rag.rag_pipeline.build_rag_chain")
def test_ask_returns_string(mock_build_chain, mock_retrieve, _lr, _ll, _lqr, mock_mlflow):
    mock_retrieve.return_value = [
        Document(
            page_content="Nettoyez les buses après chaque utilisation.",
            metadata={"chapter": 2, "chapter_title": "Laveur", "section": "ENTRETIEN"},
        )
    ]
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = "Réponse simulée."
    mock_build_chain.return_value = mock_chain
    mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
    mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

    from rag.rag_pipeline import ask
    result = ask("Comment entretenir le laveur?", log=False)
    assert isinstance(result, str)
