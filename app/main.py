from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db.base as db_base
from app.api.routes import auth, query
from rag.mlflow_logger import setup_mlflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_base.Base.metadata.create_all(bind=db_base.engine)
    setup_mlflow()
    yield


app = FastAPI(title="MediAssist Pro", version="1.0.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(query.router)


@app.get("/health")
def health():
    return {"status": "ok"}
