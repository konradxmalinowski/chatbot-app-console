import os
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from constants import SYSTEM_PROMPT

load_dotenv(verbose=True)

gemini_api_key = os.environ.get("GEMINI_API_KEY")
gemini_llm_model = os.environ.get("GEMINI_LLM_MODEL")

llm = ChatGoogleGenerativeAI(
    model=gemini_llm_model,
    google_api_key=gemini_api_key
)

parser = StrOutputParser()

chat_template_prompt = ChatPromptTemplate([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

base_chain = chat_template_prompt | llm | parser

history_state = {}

def get_session_history(session_id: str):
    if session_id not in history_state:
        history_state[session_id] = InMemoryChatMessageHistory()
    return history_state[session_id]

conversation_chain = RunnableWithMessageHistory(
    runnable=base_chain,
    get_session_history=get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

def chat_with_llm(user_prompt: str):
    config = RunnableConfig({"configurable": {"session_id": "1"}})

    response = conversation_chain.invoke(
        {"input": user_prompt},
        config=config
    )

    print("=== HISTORY ===")
    print(get_session_history("1").messages)
    print("================")

    print(f"AI: {response}")

def main():
    print("Welcome! We introduce chatbot-app v.0!")

    while True:
        user_prompt = input("You: ")

        if not user_prompt.strip():
            break

        try:
            chat_with_llm(user_prompt)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()