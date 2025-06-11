from core.config import settings

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatYandexGPT
import logging

logger = logging.getLogger(__name__)

_google_api_keys_list = []
_current_google_key_idx = 0


def create_llm(provider: str = settings.llm_provider,
               model: str = settings.llm_model_name, temperature: float = settings.temperature, top_p: float = settings.top_p):
    global _google_api_keys_list, _current_google_key_idx

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

        if not _google_api_keys_list:
            api_keys_str = settings.gemini_api_key.get_secret_value()
            if api_keys_str:
                _google_api_keys_list = [key.strip() for key in api_keys_str.split(',') if key.strip()]
            
            if not _google_api_keys_list:
                logger.error("Google API keys are not configured or are empty in settings.")
                raise ValueError("Google API keys are not configured or are invalid for round-robin.")

        if not _google_api_keys_list: # Safeguard, though previous block should handle it.
            logger.error("No Google API keys available for round-robin.")
            raise ValueError("No Google API keys available for round-robin.")

        key_index_to_use = _current_google_key_idx
        selected_api_key = _google_api_keys_list[key_index_to_use]
        
        _current_google_key_idx = (key_index_to_use + 1) % len(_google_api_keys_list)
        
        logger.info(f"Using Google API key at index {key_index_to_use} (ending with ...{selected_api_key[-4:] if len(selected_api_key) > 4 else selected_api_key}) for round-robin.")

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=selected_api_key,
            temperature=temperature,
            top_p=top_p,
            thinking_budget=1024
        )
    else:
        raise ValueError(f"Unknown model: {model}")

def create_precise_llm():
    return create_llm(temperature=0, top_p=1)
