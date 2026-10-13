"""
Nova's voice for the app (AI Buddy) — Kyutai Pocket TTS on this computer, CPU only.

    pip install pocket-tts
    python tools/nova-tts-server.py            # -> http://localhost:8765 (first run downloads the model)
    python tools/nova-tts-server.py --voice alba --port 8765

The app (app.html, js/nova-buddy.js) checks GET /health; when this server is
running it sends English replies to POST /tts {"text": "...", "lang": "en"} and
plays the WAV it gets back. Pocket TTS has no Indonesian model yet, so
Indonesian replies use the phone/browser voice instead (Web Speech API).

Why not `pocket-tts serve`: its CORS list only allows Kyutai's own sites, and
Chrome also needs the Private-Network header before a https:// page may call
http://localhost. Text is synthesised here; nothing leaves the computer.
"""
import argparse
import io
import threading
import wave

import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from pocket_tts.models.tts_model import TTSModel

ORIGINS = ["https://novaband-id.web.app", "https://novaband-id.firebaseapp.com"]
ORIGIN_RE = r"http://(localhost|127\.0\.0\.1)(:\d+)?"

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--voice", default="alba", help="built-in voice name or a .wav path")
ap.add_argument("--language", default="english")
args = ap.parse_args()

print("loading Pocket TTS (%s, voice %s)..." % (args.language, args.voice), flush=True)
model = TTSModel.load_model(language=args.language)
voice = model.get_state_for_audio_prompt(args.voice)
SR = model.config.mimi.sample_rate
lock = threading.Lock()                       # one synthesis at a time (CPU)
print("ready: http://localhost:%d  (sample rate %d Hz)" % (args.port, SR), flush=True)

app = FastAPI(title="Nova voice")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_origin_regex=ORIGIN_RE,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])


@app.middleware("http")
async def private_network(request: Request, call_next):
    # Chrome Private Network Access: a public https page calling localhost sends a preflight
    # with Access-Control-Request-Private-Network: true and needs this answer.
    resp = await call_next(request)
    if request.headers.get("access-control-request-private-network"):
        resp.headers["Access-Control-Allow-Private-Network"] = "true"
    return resp


class Req(BaseModel):
    text: str
    lang: str = "en"


@app.get("/health")
def health():
    return {"status": "ok", "engine": "pocket-tts", "languages": [args.language], "voice": args.voice}


@app.post("/tts")
def tts(r: Req):
    text = r.text.strip()[:400]
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)
    with lock:
        chunks = [c.detach().cpu().numpy().reshape(-1) for c in model.generate_audio_stream(
            model_state=voice, text_to_generate=text)]
    pcm = np.clip(np.concatenate(chunks) if chunks else np.zeros(1), -1, 1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
    return Response(buf.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
