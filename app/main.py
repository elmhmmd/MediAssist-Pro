from fastapi import FastAPI

from app.api.routes import auth, query
from app.db.base import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MediAssist Pro", version="1.0.0")

app.include_router(auth.router)
app.include_router(query.router)


@app.get("/health")
def health():
    return {"status": "ok"}
