import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from constants import SYSTEM_PROMPT

load_dotenv(verbose=True)

gemini_api_key = os.environ.get("GEMINI_API_KEY")
gemini_llm_model = os.environ.get("GEMINI_LLM_MODEL")

llm = ChatGoogleGenerativeAI(
    model=gemini_llm_model,
    google_api_key=gemini_api_key
)

parser = StrOutputParser()

def chat_with_llm(user_prompt: PromptTemplate):
    chat_template_prompt = ChatPromptTemplate([
        ("system", SYSTEM_PROMPT),
        ("user", user_prompt.format()),
    ])
    chain = chat_template_prompt | llm | parser
    response = chain.invoke({})
    print(response)

def main():
    print("Welcome! We introduce chatbot-app v.0!")

    is_running = True

    user_prompt = PromptTemplate.from_template(input("How can i help u?: "))
    chat_with_llm(user_prompt)

    while is_running:
        user_prompt = PromptTemplate.from_template(input("Your answer: "))

        if user_prompt.format() == "":
            is_running = False

        chat_with_llm(user_prompt)

if __name__ == "__main__":
    main()