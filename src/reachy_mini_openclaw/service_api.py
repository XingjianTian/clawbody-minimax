"""Private FastAPI application consumed by PsyTwin Sentinel."""

from __future__ import annotations

import os

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from reachy_mini_openclaw.config import config
from reachy_mini_openclaw.main import ClawBodyCore
from reachy_mini_openclaw.service import ClawBodyService


class StartInput(BaseModel):
    student_id: str = Field(min_length=1, max_length=100)
    identity: str = Field(default="", max_length=5000)


class TextInput(StartInput):
    message: str = Field(min_length=1, max_length=1000)


def _authorize(x_service_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("SERVICE_API_KEY", "psytwin-clawbody-local")
    if not x_service_key or x_service_key != expected:
        raise HTTPException(status_code=401, detail="invalid service key")


def _core_factory() -> ClawBodyCore:
    return ClawBodyCore(
        gateway_url=config.OPENCLAW_GATEWAY_URL,
        robot_name=config.ROBOT_NAME,
        robot_host=config.ROBOT_HOST,
        robot_port=config.ROBOT_PORT,
        enable_camera=config.ENABLE_CAMERA,
        enable_openclaw=bool(config.OPENCLAW_TOKEN),
    )


async def _complete(system_prompt: str, message: str) -> str:
    client = AsyncOpenAI(
        api_key=config.MINIMAX_API_KEY,
        base_url=config.MINIMAX_BASE_URL,
        http_client=httpx.AsyncClient(timeout=30.0, trust_env=config.HTTP_TRUST_ENV),
    )
    response = await client.chat.completions.create(
        model=config.MINIMAX_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        max_tokens=config.MINIMAX_MAX_TOKENS,
    )
    await client.close()
    return response.choices[0].message.content or ""


async def _respond_text(message: str, identity: str) -> str:
    return await _complete(identity or "你是温暖、简短、尊重学生的心宠伙伴。", message)


async def _professional_respond(message: str) -> str:
    return await _complete(
        "你是小芯 AI 的演示专业咨询师层。根据学生原话给第一层心宠生成两到三句支持建议。"
        "只输出可审核的建议摘要，不展示推理过程，不做医学诊断，不声称已经创建预警或联系真人。",
        message,
    )


service = ClawBodyService(_core_factory, _respond_text, _professional_respond)
app = FastAPI(title="PsyTwin ClawBody Internal Service", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "clawbody"}


@app.get("/v1/status", dependencies=[Depends(_authorize)])
async def status() -> dict:
    return service.status()


@app.post("/v1/session/start", dependencies=[Depends(_authorize)])
async def start_session(payload: StartInput) -> dict:
    try:
        return await service.start(payload.student_id, payload.identity)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/v1/session/stop", dependencies=[Depends(_authorize)])
async def stop_session() -> dict:
    return await service.stop()


@app.get("/v1/transcript", dependencies=[Depends(_authorize)])
async def transcript(after: int = Query(default=0, ge=0)) -> dict:
    return service.transcript_after(after)


@app.get("/v1/events", dependencies=[Depends(_authorize)])
async def events(after: int = Query(default=0, ge=0)) -> dict:
    return service.events_after(after)


@app.post("/v1/text/respond", dependencies=[Depends(_authorize)])
async def text_response(payload: TextInput) -> dict:
    try:
        response = await service.respond_text(payload.message, payload.identity)
        return {"response": response}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=os.getenv("SERVICE_HOST", "127.0.0.1"), port=int(os.getenv("SERVICE_PORT", "7862")))
