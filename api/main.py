from fastapi import FastAPI
from datetime import datetime
from .routes import deployment_router
from src import db

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": str(datetime.now())}

app.include_router(deployment_router, prefix="/deployments",
                   tags=["deployments"])
