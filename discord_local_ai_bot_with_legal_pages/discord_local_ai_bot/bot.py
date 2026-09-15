import os
import re
import time
import asyncio
from collections import defaultdict, deque

import aiohttp
import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b").strip()
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "너는 디스코드 채팅에 자연스럽고 간결하게 답하는 도우미다. "
    "상대방의 언어에 맞춰 답하고, 모르는 것은 지어내지 않는다. "
    "답변은 특별한 이유가 없으면 1~4문장으로 짧게 한다."
).strip()

# reply mode:
# mention : 서버에서는 봇을 멘션한 경우에만, DM에서는 항상 답장
# channels: ALLOWED_CHANNEL_IDS에 지정한 채널의 일반 메시지에도 답장
# all     : 봇이 볼 수 있는 모든 서버 채널 메시지에 답장 (권장하지 않음)
REPLY_MODE = os.getenv("REPLY_MODE", "mention").strip().lower()

ALLOWED_CHANNEL_IDS = {
    int(x.strip())
    for x in os.getenv("ALLOWED_CHANNEL_IDS", "").split(",")
    if x.strip().isdigit()
}

MAX_HISTORY_MESSAGES = max(2, int(os.getenv("MAX_HISTORY_MESSAGES", "10")))
MAX_REPLY_CHARS = max(100, min(1900, int(os.getenv("MAX_REPLY_CHARS", "1200"))))
USER_COOLDOWN_SEC = max(0.0, float(os.getenv("USER_COOLDOWN_SEC", "3")))
REQUEST_TIMEOUT_SEC = max(5.0, float(os.getenv("REQUEST_TIMEOUT_SEC", "90")))

# 대화 기록은 프로그램 메모리에만 저장됨. 프로그램 종료 시 사라짐.
history = defaultdict(lambda: deque(maxlen=MAX_HISTORY_MESSAGES))
last_reply_time = defaultdict(float)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


def conversation_key(message: discord.Message) -> str:
    if isinstance(message.channel, discord.DMChannel):
        return f"dm:{message.author.id}"
    return f"channel:{message.channel.id}"


def clean_message_text(message: discord.Message) -> str:
    text = message.content or ""
    if client.user:
        # <@123> 또는 <@!123> 형태의 봇 멘션 제거
        text = re.sub(rf"<@!?{client.user.id}>", "", text)
    return text.strip()


def should_reply(message: discord.Message) -> bool:
    if message.author.bot:
        return False

    # DM은 항상 허용
    if isinstance(message.channel, discord.DMChannel):
        return True

    mentioned = client.user is not None and client.user in message.mentions

    if REPLY_MODE == "mention":
        return mentioned

    if REPLY_MODE == "channels":
        return mentioned or message.channel.id in ALLOWED_CHANNEL_IDS

    if REPLY_MODE == "all":
        return True

    # 잘못된 설정이면 안전하게 mention 모드처럼 동작
    return mentioned


async def call_ollama(messages: list[dict]) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
        },
    }

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OLLAMA_URL, json=payload) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(
                    f"Ollama HTTP {response.status}: {body[:500]}"
                )
            data = await response.json()

    answer = (
        data.get("message", {}).get("content", "")
        if isinstance(data, dict)
        else ""
    )
    answer = answer.strip()

    if not answer:
        raise RuntimeError("Ollama가 빈 응답을 반환했습니다.")

    return answer[:MAX_REPLY_CHARS]


async def generate_reply(message: discord.Message) -> str:
    key = conversation_key(message)
    user_text = clean_message_text(message)

    # 첨부파일만 있고 텍스트가 없는 경우
    if not user_text:
        if message.attachments:
            user_text = "[사용자가 첨부파일을 보냈지만 현재 이 봇은 첨부파일 내용을 읽지 못합니다.]"
        else:
            user_text = "[빈 메시지]"

    display_name = getattr(message.author, "display_name", str(message.author))
    history[key].append(
        {
            "role": "user",
            "content": f"{display_name}: {user_text}",
        }
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(list(history[key]))

    answer = await call_ollama(messages)

    history[key].append({"role": "assistant", "content": answer})
    return answer


@client.event
async def on_ready():
    print("=" * 60)
    print(f"로그인됨: {client.user} (ID: {client.user.id})")
    print(f"모드: {REPLY_MODE}")
    print(f"Ollama 모델: {OLLAMA_MODEL}")
    print("Discord Local AI Bot 실행 중")
    print("=" * 60)


@client.event
async def on_message(message: discord.Message):
    if not should_reply(message):
        return

    # 사용자별 연속 호출 방지
    now = time.monotonic()
    if now - last_reply_time[message.author.id] < USER_COOLDOWN_SEC:
        return
    last_reply_time[message.author.id] = now

    try:
        async with message.channel.typing():
            answer = await generate_reply(message)

        await message.reply(
            answer,
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    except asyncio.TimeoutError:
        await message.reply(
            "로컬 AI 응답 시간이 초과됐어요. Ollama가 실행 중인지 확인해 주세요.",
            mention_author=False,
        )
    except aiohttp.ClientConnectorError:
        await message.reply(
            "로컬 AI에 연결할 수 없어요. Ollama가 실행 중인지 확인해 주세요.",
            mention_author=False,
        )
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        await message.reply(
            "답변 생성 중 오류가 발생했어요. 실행 창의 오류 메시지를 확인해 주세요.",
            mention_author=False,
        )


def main():
    if not DISCORD_TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN이 없습니다. .env.example을 .env로 복사한 뒤 "
            "Discord Bot Token을 입력하세요."
        )

    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
