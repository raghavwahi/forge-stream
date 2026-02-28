from api.app.providers.auto import AutoProvider
from api.app.providers.budget import BudgetExceededError
from api.app.providers.config import ProviderConfig
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="ForgeStream API", version="0.1.0")

_config = ProviderConfig()
_auto = AutoProvider(config=_config)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str | None = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=32_000)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        response = await _auto.generate(
            req.prompt,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    return {
        "text": response.text,
        "model": response.model,
        "provider": response.provider,
        "usage": {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
        },
        "latency_ms": response.latency_ms,
    }


@app.get("/budget")
async def budget_status():
    return _auto.budget.get_status()
