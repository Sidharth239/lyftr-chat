# 2–3 minute narrated demo (target 2:50)

Before recording: verify the live backend using `python scripts/verify.py YOUR_BACKEND_URL`. Warm up the service (open `/health`); leave API health, deployed frontend, public GitHub repo, and browser DevTools Network ready. Use a **fresh first prompt** that you have not already tested, so the first request is a real cache miss. Keep system prompt empty. Do not display .env or secret dashboard values. You can use a short unique word in the first question to guarantee a fresh cache key.

| Time | What to show | Suggested narration |
|---|---|---|
| 0:00–0:15 | Live frontend URL and health JSON via API health link | "This is Relay, my React and FastAPI chatbot. The backend health endpoint shows two configured API keys and caching enabled." |
| 0:15–0:35 | In normal mode send `My favorite planet is Saturn. Remember it. Reply in one sentence. Demo ref [unique word].` | "The first request is live inference. Each reply displays the model, server latency and input/output tokens for just this request, with the key ID and fallback count." |
| 0:35–0:55 | Same session: send `Which planet did I say was my favorite?` | "The client sends only the new message. The backend reads earlier messages from SQLite, so it remembers Saturn." |
| 0:55–1:15 | New chat, paste the EXACT original first message | "A fresh session with the identical first prompt hits the LiteLLM cache. The response and token counts are identical, and no provider key is used. Compare the measured latency." |
| 1:15–1:45 | Select `Key 1 — rate limit (429)` and send `What is 7 plus 8?`. Network > POST /chat > Headers, Response. | "The request has X-Simulate-Failure: key_1=429. The gateway skips the failing first key, calls the next key, and returns a real answer. Key 2 and one fallback attempt confirm failover." |
| 1:45–2:05 | Select `Key 1 — server error (500)`, send `What is 9 plus 6?`. Then choose `All keys — rate limit`, send `This request must not be saved.` | "The same fallback works for a 500. When all keys fail, the API returns HTTP 503 and the UI displays a readable error instead of crashing." |
| 2:05–2:25 | Click View stored history, show GET `/sessions/{session_id}/messages` in Network or open the URL in a tab. Show the failed turn is absent. | "The history endpoint returns successful messages and assistant metadata in order. The failed request was not persisted. This history lives on a persistent SQLite volume." |
| 2:25–2:50 | Public GitHub repo: show backend/frontend, Dockerfiles, Compose, Makefile and README; mention tests | "Both services use multi-stage Dockerfiles, the SQLite volume persists across restarts, and make up starts the stack locally. The README includes verification and design decisions." |

Use actual observed results; if provider latency, key behavior or cache results differ, fix and repeat before recording. Do not claim a test result or persistent restart test unless you ran it. All three endpoints are shown by the above flow. If time allows, briefly show 422 from an invalid request in the verification script output.

## Record on Windows

Use OBS Studio (https://obsproject.com/) with Display Capture/Window Capture and microphone audio, or Windows 11 Snipping Tool screen recording if microphone capture is available. Make a short mic test. Hide notifications, close private tabs, zoom browser to a readable size, and keep API responses expanded. Stop at 2–3 minutes and save as MP4 (OBS can record MKV then File > Remux Recordings to MP4).

## Upload and submission

Upload to Google Drive (https://drive.google.com/), right-click file > Share > General access > Anyone with the link > Viewer > Copy link. Test it signed out. Submit that link, the frontend URL, backend base URL and public repository URL through the assignment form; if the form requires a file upload instead, use the recording itself. Form: https://docs.google.com/forms/d/e/1FAIpQLSfaPS5_NliZuEjhYXppeafBrNM9u0hp-q-vT8vDuv9GU-0THA/viewform
