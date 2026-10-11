"""
main.py - the FastAPI backend.

It does only three things:
  1. Shows the web page          (GET  /)
  2. Says "I'm alive" to Render  (GET  /health)
  3. Runs the research pipeline  (POST /api/research)
"""

import json
import queue
import threading

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()  # reads your API keys from the .env file (must run before importing pipeline)

from pipeline import run_research_pipeline  # noqa: E402

app = FastAPI()

# Files inside the "static" folder (style.css, script.js) are served at /static/...
app.mount("/static", StaticFiles(directory="static"), name="static")


class ResearchRequest(BaseModel):
    topic: str


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/research")
def research(request: ResearchRequest):
    """
    The pipeline takes minutes, so we do NOT wait and send one big answer.
    Instead we send small JSON messages (one per line) as each step finishes.
    The browser reads them live and updates the progress cards.
    """
    messages = queue.Queue()  # the pipeline puts messages in, the stream takes them out

    def send_progress(event, data):
        messages.put({"event": event, **data})

    def run_in_background():
        try:
            state = run_research_pipeline(request.topic, on_event=send_progress)
            messages.put({
                "event": "finished",
                "report": str(state["report"]),
                "feedback": str(state["feedback"]),
            })
        except Exception as error:
            messages.put({"event": "error", "message": str(error)})
        messages.put(None)  # None means "we are done"

    threading.Thread(target=run_in_background, daemon=True).start()

    def stream():
        while True:
            try:
                message = messages.get(timeout=15)
            except queue.Empty:
                # Nothing new for 15s: send a tiny "ping" so the connection stays open
                yield json.dumps({"event": "ping"}) + "\n"
                continue
            if message is None:
                break
            yield json.dumps(message) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")