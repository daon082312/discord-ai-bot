from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors
from pydantic import BaseModel, Field

load_dotenv()


class ScoreSet(BaseModel):
    aim: int = Field(ge=0, le=100)
    movement: int = Field(ge=0, le=100)
    positioning: int = Field(ge=0, le=100)
    utility: int = Field(ge=0, le=100)
    decision_making: int = Field(ge=0, le=100)


class Event(BaseModel):
    timestamp: str
    category: Literal[
        "aim", "movement", "positioning", "utility",
        "decision_making", "teamplay", "other"
    ]
    severity: Literal["positive", "low", "medium", "high"]
    observation: str
    feedback: str
    confidence: float = Field(ge=0, le=1)


class ValorantAnalysis(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    summary: str
    scores: ScoreSet
    events: list[Event]
    top_priorities: list[str]
    limitations: list[str]


PROMPT = """
당신은 VALORANT 경기 후 코칭 전문가입니다.
첨부된 클립 전체를 시간 순서대로 분석하세요.

원칙:
- 실제 영상에서 확인되는 내용만 말합니다.
- 보이지 않는 적, 스킬, 팀원의 의도, 랭크를 추측하지 않습니다.
- 불확실하면 confidence를 낮게 기록합니다.
- 가능한 경우 MM:SS timestamp를 기록합니다.
- 피드백은 한국어로 작성합니다.
- 다음 게임에서 바로 적용할 수 있는 구체적인 조언을 합니다.

평가 항목:
Aim, Movement, Positioning, Utility, Decision Making, Teamplay.

reaction time(ms), DPI, 프레임 단위 counter-strafe timing처럼
영상만으로 정확히 측정할 수 없는 것을 측정했다고 주장하지 마세요.

overall_score와 각 점수는 0~100,
events는 시간 순서대로,
top_priorities는 최대 3개입니다.
"""


def _wait_for_file(client, uploaded):
    for _ in range(120):
        current = client.files.get(name=uploaded.name)
        state = getattr(getattr(current, "state", None), "name", None)

        if state == "ACTIVE":
            return current
        if state == "FAILED":
            raise RuntimeError("Gemini 영상 처리에 실패했습니다.")

        time.sleep(2)

    raise RuntimeError("영상 처리 시간이 너무 오래 걸렸습니다.")


def _models():
    primary = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
    fallback = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")
    result = [primary]
    if fallback and fallback not in result:
        result.append(fallback)
    return result


def analyze_video(video_path: Path) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(".env에 GEMINI_API_KEY가 없습니다.")

    client = genai.Client(api_key=api_key)
    uploaded = None
    last_error = None

    try:
        uploaded = client.files.upload(file=video_path)
        uploaded = _wait_for_file(client, uploaded)

        for model in _models():
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=[uploaded, PROMPT],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=ValorantAnalysis,
                            temperature=0.2
                        )
                    )

                    if not response.text:
                        raise RuntimeError("Gemini가 빈 응답을 반환했습니다.")

                    result = ValorantAnalysis.model_validate_json(
                        response.text
                    ).model_dump()
                    result["model_used"] = model
                    return result

                except errors.APIError as exc:
    last_error = exc
    error_text = str(exc)

    # 서버 혼잡: 같은 모델 재시도
    if "503" in error_text:
        time.sleep(2 + attempt * 3)
        continue

    # 무료 quota 초과: 다음 모델로 이동
    if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
        print(f"{model} quota 초과 → 다음 모델로 전환")
        break

    raise

        raise RuntimeError(
            f"Gemini 서버가 혼잡합니다. 마지막 오류: {last_error}"
        )

    finally:
        if uploaded is not None:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass
