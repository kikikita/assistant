from pydantic import BaseModel


class AgentRequest(BaseModel):
    message: str
    user_id: int


class AgentResponse(BaseModel):
    answer: str
