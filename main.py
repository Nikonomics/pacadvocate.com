from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import legislation, health
from models.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SNF Leg Tracker",
    description="Legislative tracking platform for monitoring bills and regulations",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(legislation.router, prefix="/api/v1", tags=["legislation"])

@app.get("/")
async def root():
    return {"message": "SNF Leg Tracker API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)