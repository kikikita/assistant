from core.config import settings
from services.google import ApiKeyPool

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

logger = logging.getLogger(__name__)

_pool = ApiKeyPool()


def create_llm(provider: str = settings.llm_provider,
               model: str = settings.llm_model_name, temperature: float = settings.temperature, top_p: float = settings.top_p):

    if provider.lower() == "openai":
        logger.info(f"SET LLM {provider} {model}")
        return ChatOpenAI(
            model_name=model,
            openai_api_key=settings.assistant_api_key.get_secret_value(),
            temperature=temperature,
            streaming=True,
            top_p=top_p,
            openai_proxy=settings.openai_proxy,
        )
    elif provider.lower() == "google":
        logger.info(f"SET LLM {provider} {model}")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=_pool.get_key_sync(),
            temperature=temperature,
            top_p=top_p,
            thinking_budget=1024
        )
    else:
        raise ValueError(f"Unknown model: {model}")

def create_precise_llm():
    return create_llm(temperature=0, top_p=1)
