from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

import app.db.base as db_base
from app.api.routes import admin, auth, query
from rag.mlflow_logger import setup_mlflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_base.Base.metadata.create_all(bind=db_base.engine)
    setup_mlflow()
    yield


app = FastAPI(title="MediAssist Pro", version="1.0.0", lifespan=lifespan)

Instrumentator().instrument(app).expose(app)

app.include_router(auth.router)
app.include_router(query.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
