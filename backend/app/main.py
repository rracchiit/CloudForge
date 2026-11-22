
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import apps
from app.api import github
from app.api import deployments

app = FastAPI(
    title="CloudForge API",
    version="0.3.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(apps.router)
app.include_router(github.router)
app.include_router(deployments.router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "CloudForge API",
    }
