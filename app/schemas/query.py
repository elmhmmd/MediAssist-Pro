from datetime import datetime

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str


class QueryOut(BaseModel):
    id: int
    query: str
    reponse: str
    created_at: datetime

    model_config = {"from_attributes": True}
