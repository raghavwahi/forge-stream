from fastapi import FastAPI

from app.routers.work_items import router as work_items_router

app = FastAPI(title="ForgeStream API", version="0.1.0")

app.include_router(work_items_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
