from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import get_connection
from .routers import data, graph, upload, query
from .services.graph import get_graph_client

logging.basicConfig(level=logging.INFO)

settings = get_settings()
graph_client = get_graph_client()

app = FastAPI(title="UFDR Forensic Toolkit", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def ensure_database() -> None:
    with get_connection() as conn:
        conn.execute("SELECT 1")


@app.on_event("shutdown")
def close_graph_client() -> None:
    graph_client.close()


@app.get("/")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(upload.router)
app.include_router(data.router)
app.include_router(graph.router)
app.include_router(query.router)
