# Deployment and submission guide

The assignment requires separate public, connected frontend/backend URLs, SQLite on persistent disk, a public GitHub repository and a narrated 2–3 minute screen recording. No real API keys are included in this source archive. You need to complete these steps in your accounts.

## 1. Local setup (Groq)

The local Docker stack has successfully passed live backend verification using Groq GPT-OSS 20B. No provider code changes are required. If setting up from scratch:

1. Sign in at https://console.groq.com/keys and create two distinct keys with access to `openai/gpt-oss-20b`.
2. Copy `.env.example` to `.env` (only if `.env` does not already exist). Set the real keys and `LLM_MODEL=groq/openai/gpt-oss-20b`. Keep keys secret. In `.env.example` use the same model but placeholder keys.
3. Start Docker Desktop and run `docker compose up --build -d` (or `make up`). If only changing backend environment variables, use `docker compose up -d --force-recreate backend`.
4. Check `docker compose ps`, http://localhost:8000/health and http://localhost:3000.
5. Verify all endpoints from the project root. On Windows without Python installed:

   ```powershell
   Get-Content scripts/verify.py -Raw | docker compose exec -T backend python - http://localhost:8000
   ```

   With local Python installed, `python scripts/verify.py http://localhost:8000` also works.

Both keys can belong to the same Groq organization for simulated failover; they may share organization-level quotas. Free-tier access is subject to availability and limits. If inference fails, inspect `docker compose logs --tail=100 backend` and check the model and key permissions in Groq Console. A healthy backend does not prove provider access.

## 2. Public GitHub repository

Create an empty public repository at https://github.com/new named `lyftr-chat` (do not initialize README). From the extracted project root:

```sh
git init
git check-ignore .env
git add .
git status --short
```

Confirm `.env` is ignored and not staged; `.env.example` should have placeholder keys only. Then continue:

```sh
git commit -m "Build resilient LLM chatbot"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/lyftr-chat.git
git push -u origin main
```

Check `git status` before committing. `.env`, local databases, and node_modules should not be included. Check the repo in a private browser window. For deployment use the steps below (no credentials in GitHub).

## 3. Backend on Render (persistent storage)

1. At https://dashboard.render.com/ select New > Web Service, connect your GitHub repository and pick `main`.
2. Root Directory: `backend`; Language/Runtime: Docker; Dockerfile path relative to root: `./Dockerfile`. Use a paid instance with disk support. A free ephemeral filesystem does not satisfy the persistence requirement.
3. Add a persistent disk mounted at `/data` (e.g. 1 GB). Configure one instance; do not set a multi-worker start command.
4. Set environment variables in the dashboard:

   ```text
   LLM_API_KEYS=<your two real Groq keys separated by a comma>
   LLM_MODEL=groq/openai/gpt-oss-20b
   DATABASE_URL=sqlite:////data/app.db
   ALLOWED_ORIGINS=http://localhost:3000
   ENABLE_FAILURE_SIMULATION=true
   LLM_TIMEOUT_SECONDS=30
   ```

   Use the exact model ID confirmed locally: `groq/openai/gpt-oss-20b`. Enter the real keys only in the backend service environment settings, never in frontend settings. Do not include the angle brackets around the key values. Render sets PORT; the Dockerfile binds to it automatically. Health check path: `/health`.
5. Deploy. Copy the actual `https://...onrender.com` URL and open `/health`. It should show `status: ok`, at least two keys configured and cache enabled. Health checks configuration, not provider quotas; test `/chat` as well.

Render docs: https://render.com/docs/web-services and https://render.com/docs/disks. A paid persistent disk is necessary on Render; if you choose a different host use a mounted persistent volume. Check plan pricing before purchasing.

## 4. Frontend on Render Static Site

1. New > Static Site; choose the same GitHub repo, branch `main`.
2. Root Directory: `frontend`; Build Command: `npm install && npm run build`; Publish Directory: `dist`.
3. Environment variable `VITE_API_URL` = the actual backend HTTPS base URL (without `/chat` or `/health`). Deploy and copy the frontend URL.
4. Back in the backend service, set `ALLOWED_ORIGINS` to the exact frontend origin (no trailing slash), optionally followed by `,http://localhost:3000`. Save/redeploy. If the backend was changed after testing, repeat tests because the in-memory cache resets.
5. Open the frontend and send a fresh prompt. Run the live verification script against the actual public backend base URL. If Python is not installed on Windows, use your running local Docker container to test the remote backend:

   ```powershell
   Get-Content scripts/verify.py -Raw | docker compose exec -T backend python - https://YOUR-BACKEND.onrender.com
   ```

   Alternatively use `python scripts/verify.py https://YOUR-BACKEND.onrender.com` with local Python. Replace the placeholder URL before running either command. Inspect Network responses if anything fails.

## 5. Confirm persistence and finalize

From a successful live verification run copy the printed session ID and visit `https://YOUR-BACKEND.onrender.com/sessions/SESSION-ID/messages`. Restart the backend service and visit the same endpoint: the messages should still be present. Confirm `/health` works. Repeat cache demonstration after restarting (cache is intentionally in memory).

Replace README Live URLs placeholders with actual frontend, backend, GitHub and demo URLs. Review Setup Used for accuracy and commit/push. Any subsequent deployment clears the in-memory cache; perform the final video after services finish deploying. Public URLs must not ask for a login.

## 6. Record and submit

Follow [DEMO.md](DEMO.md), use your voice and show the deployed URLs (not just localhost). Refer to Groq and GPT-OSS 20B (`groq/openai/gpt-oss-20b`) in the narration instead of Gemini. Show all three endpoints, a live response, a cache hit in a fresh session, and `X-Simulate-Failure` with a successful key switch. Show the clean 503 and session history if time allows. Upload the recording to Google Drive with General access > Anyone with the link > Viewer, or use an unlisted YouTube video if the form permits video links. Test the shared link in an incognito window. Do not show API keys, private environment variables or account details. If the form asks for an upload rather than a link, follow its actual instructions.

Submit all four links through the exact form linked in the PDF:
https://docs.google.com/forms/d/e/1FAIpQLSfaPS5_NliZuEjhYXppeafBrNM9u0hp-q-vT8vDuv9GU-0THA/viewform

The assignment deadline is 24 hours from receipt. The form's fields were not independently inspected; use the actual form labels. Keep services active and available during evaluation, then disable simulation/remove the public demo when no longer needed to avoid abuse/cost.
