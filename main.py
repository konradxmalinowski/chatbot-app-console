import logging
import os
import sys

from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPIError, PermissionDenied
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_google_genai import ChatGoogleGenerativeAI

from constants import DEFAULT_SESSION_ID, MAX_INPUT_LENGTH, SYSTEM_PROMPT

logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")

_PLACEHOLDER_MARKERS = [
    "[NAZWA FIRMY",
    "[GŁÓWNY CEL",
    "[EMAIL/LINK",
    "[Temat",
]


def _validate_env() -> tuple[str, str]:
    """Read and validate required environment variables. Exits on failure."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    llm_model = os.environ.get("GEMINI_LLM_MODEL", "").strip()

    if not api_key:
        print(
            "Missing required env var: GEMINI_API_KEY. "
            "Copy .env.example to .env and fill in your key."
        )
        sys.exit(1)

    if not llm_model:
        print(
            "Missing required env var: GEMINI_LLM_MODEL. "
            "Copy .env.example to .env and set the model name (e.g. gemini-2.5-flash)."
        )
        sys.exit(1)

    return api_key, llm_model


def _check_system_prompt_placeholders() -> None:
    """Warn if SYSTEM_PROMPT still contains unfilled template placeholders."""
    found = [marker for marker in _PLACEHOLDER_MARKERS if marker in SYSTEM_PROMPT]
    if found:
        print(
            "Warning: SYSTEM_PROMPT contains unfilled placeholders: "
            + ", ".join(found)
            + ". Customize constants.py before deploying."
        )


def build_chain():
    """Build and return (conversation_chain, history_state)."""
    load_dotenv()

    api_key, llm_model = _validate_env()
    _check_system_prompt_placeholders()

    llm = ChatGoogleGenerativeAI(model=llm_model, google_api_key=api_key)

    parser = StrOutputParser()

    chat_template_prompt = ChatPromptTemplate(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ]
    )

    base_chain = chat_template_prompt | llm | parser

    history_state: dict[str, InMemoryChatMessageHistory] = {}

    def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
        if session_id not in history_state:
            history_state[session_id] = InMemoryChatMessageHistory()
        return history_state[session_id]

    conversation_chain = RunnableWithMessageHistory(
        runnable=base_chain,
        get_session_history=get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    return conversation_chain, history_state


def chat_with_llm(conversation_chain, user_prompt: str) -> str:
    """Send user_prompt to the LLM and return the full response string."""
    config = RunnableConfig({"configurable": {"session_id": DEFAULT_SESSION_ID}})

    try:
        response_parts = []
        for chunk in conversation_chain.stream({"input": user_prompt}, config=config):
            print(chunk, end="", flush=True)
            response_parts.append(chunk)
        print()  # trailing newline after stream
        return "".join(response_parts)
    except PermissionDenied:
        logging.error("API key invalid or quota exceeded.")
        return ""
    except GoogleAPIError:
        logging.error("Network error — check your connection.")
        return ""
    except Exception as exc:
        logging.error("Unexpected error: %s", exc)
        return ""


def main():
    conversation_chain, _ = build_chain()

    print("Welcome! We introduce chatbot-app v.0!")

    while True:
        user_prompt = input("You: ")

        if not user_prompt.strip():
            break

        if len(user_prompt) > MAX_INPUT_LENGTH:
            print(
                f"Warning: input exceeds {MAX_INPUT_LENGTH} characters. "
                "Please shorten your message and try again."
            )
            continue

        print("AI: ", end="", flush=True)
        chat_with_llm(conversation_chain, user_prompt)


if __name__ == "__main__":
    main()
