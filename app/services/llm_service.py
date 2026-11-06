import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")


def get_llm(
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1000,
) -> ChatGroq:
    api_key = os.getenv("GroqKEY", "")
    if not api_key:
        raise RuntimeError("Set GroqKEY in the project .env file before invoice analysis.")
    model_name = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    return ChatGroq(
        api_key=api_key,
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class _LazyLLM:
    """Lazy LLM proxy so importing the module doesn't require GroqKEY to be pre-set."""

    def __getattr__(self, name: str):
        return getattr(get_llm(), name)

    def with_structured_output(self, *args, **kwargs):
        return get_llm().with_structured_output(*args, **kwargs)


llm = _LazyLLM()

