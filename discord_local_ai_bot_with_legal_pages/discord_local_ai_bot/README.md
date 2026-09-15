# Discord Local AI Auto-Reply Bot

Discord 공식 **Bot 계정**으로 메시지를 받고, 답변 생성은 PC의 **Ollama 로컬 모델**로 수행하는 예제입니다.

기본값은 안전하게 다음 메시지에만 답합니다.

- 봇에게 온 DM
- 서버에서 봇이 직접 멘션된 메시지

`.env`에서 지정 채널 전체 자동응답도 켤 수 있습니다.

## 1. 필요한 것

- Windows 10/11
- Python 3.11 이상 권장
- Discord 계정 및 본인이 봇을 추가할 수 있는 서버
- Ollama

## 2. Ollama 설치와 모델 준비

Ollama를 설치한 뒤 PowerShell/명령 프롬프트에서 원하는 모델을 받습니다.

예:

```powershell
ollama run gemma4:e4b
```

모델이 정상적으로 대답하면 `Ctrl+C`로 대화 화면을 종료해도 Ollama 서비스는 일반적으로 백그라운드에서 동작합니다.

PC 사양이 부족하면 더 작은 모델을 `.env`의 `OLLAMA_MODEL`에 지정하세요.

## 3. Discord Bot 만들기

1. Discord Developer Portal에서 새 Application 생성
2. `Bot` 메뉴에서 Bot 생성
3. Bot Token 발급
4. **Message Content Intent**를 사용하도록 설정
5. OAuth2/Installation에서 Bot을 본인의 테스트 서버에 추가
6. 최소 권한:
   - View Channels
   - Send Messages
   - Read Message History

Bot Token은 일반 Discord 사용자 토큰이 아닙니다.

## 4. 환경설정

`.env.example`을 복사해서 파일명을 `.env`로 바꿉니다.

```text
DISCORD_TOKEN=여기에_봇_토큰
OLLAMA_MODEL=gemma4:e4b
REPLY_MODE=mention
```

토큰을 GitHub에 업로드하지 마세요.

### 응답 모드

`REPLY_MODE=mention`

- DM: 자동 응답
- 서버: 봇을 `@멘션`한 경우만 응답

`REPLY_MODE=channels`

- 위 조건 +
- `ALLOWED_CHANNEL_IDS`에 지정한 채널의 모든 일반 메시지에 응답

예:

```text
REPLY_MODE=channels
ALLOWED_CHANNEL_IDS=123456789012345678,987654321098765432
```

`REPLY_MODE=all`

- 봇이 읽을 수 있는 거의 모든 메시지에 답하려고 합니다.
- 채팅 도배 가능성이 있어 테스트 외에는 권장하지 않습니다.

## 5. 실행

Windows에서는 `run_windows.bat`을 더블클릭하면 됩니다.

또는 직접:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

## 6. 현재 구현된 기능

- Discord 공식 Bot API 사용
- Ollama 로컬 AI 답변
- DM 자동응답
- 멘션 자동응답
- 특정 채널 자동응답 옵션
- 최근 대화 문맥 유지
- 사용자별 cooldown
- 봇 메시지 무시
- 최대 답변 길이 제한
- `.env` 기반 설정
- Bot Token 코드에 하드코딩하지 않음

## 7. 중요한 제한

이 프로그램은 일반 Discord 사용자 계정을 자동조작하는 self-bot이 아닙니다.  
Discord에서는 일반 사용자 계정의 자동화를 금지하므로 공식 Bot 계정을 사용해야 합니다.

또한 "로컬 AI"는 **답변 생성 모델이 로컬에서 실행된다는 의미**입니다. Discord 메시지를 주고받기 위해서는 당연히 Discord 서버와 인터넷 연결이 필요합니다.

## 8. 다음 단계로 추가하기 좋은 기능

- GUI에서 ON/OFF
- 특정 친구/사용자에게만 반응
- 특정 시간대에만 자동응답
- 사용자별 다른 말투
- 대화기록 SQLite 저장
- 이미지 첨부 분석용 로컬 비전 모델
- `/ai`, `/pause`, `/resume` 슬래시 명령
- 답변 전 미리보기/승인 모드
- Windows 시작 시 자동 실행
