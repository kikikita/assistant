from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas.agent import AgentRequest, AgentResponse
from agent.llm_agent import get_assistant_response
from crud.conversation_history import save_user_message, save_bot_message
from db.session import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/dialog/agent", response_model=AgentResponse)
async def dialog_agent(request: AgentRequest, db: Session = Depends(get_db)):
    """
    Возвращает ответ ассистента на произвольное сообщение пользователя.
    Сохраняет историю разговора в базу данных.
    """
    try:        
        logger.info(f"User {request.user_id} sent message: {request.message}")
        answer = await get_assistant_response(
            request.message, str(request.user_id), db
        )
        
        if not answer:
            answer = "Извините, не удалось получить ответ."
            
        session = save_user_message(
            db=db,
            tg_user_id=request.user_id,
            message=request.message
        )
        
        save_bot_message(
            db=db,
            session_id=session.id,
            message=answer
        )
        logger.info(f"Assistant answered to user {request.user_id}: {answer}")
        return AgentResponse(answer=answer)
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Assistant error: {exc}")
