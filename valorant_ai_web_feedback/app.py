from pathlib import Path
import shutil
import tempfile
import uuid

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from analyzer import analyze_video
from feedback_store import save_feedback

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="VALORANT AI Coach")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class FeedbackRequest(BaseModel):
    analysis_id: str = Field(min_length=1, max_length=100)
    target_type: str = Field(pattern="^(overall|event)$")
    event_index: int | None = Field(default=None, ge=0)
    event_timestamp: str | None = Field(default=None, max_length=20)
    event_category: str | None = Field(default=None, max_length=50)
    rating: str = Field(min_length=1, max_length=30)
    categories: list[str] = Field(default_factory=list, max_length=10)
    comment: str = Field(default="", max_length=2000)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 없습니다.")

    suffix = Path(file.filename).suffix.lower()
    allowed = {".mp4", ".mov", ".webm", ".avi", ".mkv"}

    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 영상 형식입니다."
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = Path(tmp.name)
            shutil.copyfileobj(file.file, tmp)

        result = analyze_video(temp_path)
        result["analysis_id"] = uuid.uuid4().hex
        return result

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        try:
            await file.close()
        except Exception:
            pass

        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


@app.post("/feedback")
async def feedback(payload: FeedbackRequest):
    if payload.target_type == "overall":
        if payload.rating not in {"helpful", "partial", "not_helpful"}:
            raise HTTPException(status_code=400, detail="잘못된 전체 평가입니다.")
    else:
        if payload.rating not in {"up", "down"}:
            raise HTTPException(status_code=400, detail="잘못된 장면 평가입니다.")
        if payload.event_index is None:
            raise HTTPException(status_code=400, detail="event_index가 필요합니다.")

    feedback_id = save_feedback(payload.model_dump())
    return {
        "ok": True,
        "feedback_id": feedback_id,
        "message": "피드백이 저장되었습니다."
    }
