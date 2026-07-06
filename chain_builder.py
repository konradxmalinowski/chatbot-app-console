"""Shared LangChain LCEL chain construction for the CLI (``main.py``) and the REST
API (``api/main.py``).

Keeps the prompt templates and the RAG citation-formatting logic in one place so
both entry points build byte-for-byte identical prompts, rather than maintaining
two copies that could quietly drift. The chat model itself is built by
``llm_provider.get_llm()`` (see that module) — this file no longer constructs it
directly, so there is exactly one code path for building the chat model.
"""

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from constants import RAG_SYSTEM_PROMPT_SUFFIX, RAG_TOP_K, SYSTEM_PROMPT


def format_retrieved_context(chunks: list[Document]) -> str:
    """Render retrieved chunks as a citation-ready context block for the prompt."""
    if not chunks:
        return "(No relevant context was found for this question.)"

    parts = []
    for chunk in chunks:
        source = chunk.metadata.get("source", "unknown")
        parts.append(f"[source: {source}]\n{chunk.page_content}")
    return "\n\n".join(parts)


def build_plain_prompt() -> ChatPromptTemplate:
    """Non-RAG system prompt + history + user input."""
    return ChatPromptTemplate(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ]
    )


def build_rag_prompt() -> ChatPromptTemplate:
    """RAG system prompt (with citation instructions) + history + context + input."""
    return ChatPromptTemplate(
        [
            ("system", SYSTEM_PROMPT + RAG_SYSTEM_PROMPT_SUFFIX),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "Retrieved context:\n{context}\n\nQuestion: {input}"),
        ]
    )


def build_base_chain(llm, rag_store=None):
    """Return the LCEL runnable used by the CLI: prompt | llm | parser.

    When ``rag_store`` is given, retrieval happens implicitly inside the chain on
    every invocation (opaque to the caller) — this is what ``main.py``'s ``--rag``
    mode uses.

    The REST API's ``/chat/rag`` route does NOT use this variant: it needs the
    retrieved chunks themselves to populate response citations, so it retrieves
    explicitly once and uses ``build_rag_prompt()`` + ``build_rag_answer_chain()``
    instead (see ``api/main.py``) rather than triggering a second, redundant
    retrieval call.
    """
    parser = StrOutputParser()

    if rag_store is not None:
        from rag.retriever import retrieve

        def _retrieve_context(inputs: dict) -> str:
            chunks = retrieve(rag_store, inputs["input"], k=RAG_TOP_K)
            return format_retrieved_context(chunks)

        return (
            RunnablePassthrough.assign(context=RunnableLambda(_retrieve_context))
            | build_rag_prompt()
            | llm
            | parser
        )

    return build_plain_prompt() | llm | parser


def build_rag_answer_chain(llm):
    """RAG prompt | llm | parser, expecting the caller to supply a pre-computed
    ``context`` string in the chain input (alongside ``input``).

    Used by the REST API, which performs retrieval explicitly (once) so it can both
    feed the prompt and return the retrieved chunks as citations in the response.
    """
    return build_rag_prompt() | llm | StrOutputParser()
