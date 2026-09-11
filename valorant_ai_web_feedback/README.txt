VALORANT AI Coach Web + Feedback

1. CMD에서 이 폴더로 이동
2. python -m pip install -r requirements.txt
3. .env.example을 복사해서 .env로 변경
4. .env에 Gemini API key 입력
5. python -m uvicorn app:app --reload
6. http://127.0.0.1:8000 접속

피드백 저장 위치:
data/feedback.jsonl

주의:
Render 같은 클라우드에서는 로컬 파일이 영구 보존되지 않을 수 있습니다.
공개 서비스에서는 Supabase/PostgreSQL 같은 DB로 교체하는 것을 권장합니다.
