import logging
from typing import List, Dict, Any

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
)
from langchain_core.runnables import RunnableConfig
from agent.resume import get_user_resume, get_resume_scheme
from agent.llm_graph import graph
from crud.conversation_history import get_conversation_history, get_user_session_for_conversation
from crud.user import get_user_by_tg_id
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _convert_db_history_to_messages(history: List[Dict[str, Any]]) -> List[HumanMessage | AIMessage]:
    """
    Конвертирует историю из базы данных в формат сообщений LangChain.
    """
    messages = []
    for msg in history:
        if msg["role"] == "human":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "bot":
            messages.append(AIMessage(content=msg["content"]))
    return messages


async def get_assistant_response(question: str, user_id: str, db: Session) -> str | None:
    """
    Внешняя точка входа для бота.
    Использует историю разговора из базы данных.
    """
    try:
        config = RunnableConfig({"configurable": {"thread_id": user_id}})

        current_resume = await get_user_resume(user_id)
        logger.debug("User %s resume fetched: %s", user_id, current_resume)

        resume_scheme = await get_resume_scheme()
        logger.debug("User %s resume scheme fetched: %s", user_id, resume_scheme)

        user = get_user_by_tg_id(db, int(user_id))
        if user:
            session = get_user_session_for_conversation(db, user.id)
            history = get_conversation_history(db, session.id, limit=50)
            past_messages = _convert_db_history_to_messages(history)
        else:
            past_messages = []

        all_messages = past_messages + [HumanMessage(content=question)]

        response = await graph.ainvoke(
            {
                "user_id": user_id,
                "current_resume": current_resume,
                "resume_scheme": resume_scheme,
                "messages": all_messages,
                "session": db
            },
            config=config,
        )

        final_msg = response["messages"][-1].content if response else None
        logger.debug("Assistant final content: %s", final_msg)
        return final_msg

    except Exception as exc:
        logger.exception("Failed to get assistant response: %s", exc)
        raise
