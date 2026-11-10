# Writing Lab — GitHub Pages + Render

`docs/index.html` is the frontend. FastAPI computes metrics and optionally requests AI hints. W1–W3 are teacher-authored fictional examples. No learner drafts or credentials belong in Git.

## Status

Prepared locally; no public deployment has been claimed. Confirm the target repository and Render workspace, service name, region and approved plan before provisioning. Pages origin: `https://dashoufajia.github.io`; the site path depends on the selected repository.

`render.yaml` is a draft using a single Free instance in Singapore. Free instances have idle spin-down and resource limits. Paid hosting needs explicit approval. Gateway model usage is charged separately under the user's provider plan.

## Publication files

`scripts/prepare_release.py` creates an allowlisted publication tree in `work/publish`. It excludes local `.env`, virtual environments, course PDFs/prompts, game pages, browser backups, scratch files and logs. Its root `03_Data.json` contains only W1–W3 and Writing Lab calculation fixtures. The original full course data is left untouched.

Audit before staging, after staging and after committing:

```sh
python scripts/audit_publication.py --root .
```

When available, add `--private-env /path/to/private/.env` to scan for exact private values as well. The audit checks allowlisted files, credential patterns, staged Git blobs and all reachable historical Git blobs without printing detected values. A failed audit stops publication. Stage explicit reviewed files from PUBLICATION_MANIFEST.json, not an indiscriminate project-wide add. Never force-push or overwrite unrelated repository files.

## Render Web Service

Repository: approved target. Branch: `main`. Runtime: Python. Root Directory: leave blank (repository root). Health Check Path: `/healthz`. Select the approved plan and region.

Build command, one line:

```sh
python -m pip install -r starter/requirements.txt && python -m spacy download en_core_web_sm && python -m nltk.downloader -d nltk_data cmudict && python scripts/check_runtime.py
```

Start command (space before `$PORT`):

```sh
python -m uvicorn starter.app:app --host 0.0.0.0 --port $PORT
```

| Environment variable | Value / source |
|---|---|
| PYTHON_VERSION | 3.12.14 |
| APP_ENV | production |
| NLTK_DATA | ./nltk_data |
| ALLOWED_ORIGINS | https://dashoufajia.github.io (origin only, no repository path) |
| ANTROUTER_BASE_URL | https://api.antrouter.io/v1 |
| ANTROUTER_MODEL | gpt-6.1-sol |
| ANTROUTER_API_KEY | Secret entered in Render Environment, never in Git or docs/config.js |
| CLASSROOM_DEMO_CODE | Secret classroom code entered in Render Environment |
| AI_REQUESTS_PER_MINUTE | 5 per client |
| AI_TOTAL_PER_MINUTE | 30 aggregate |
| AI_TOTAL_PER_DAY | 200 aggregate per rolling 24 hours |
| ANALYSIS_REQUESTS_PER_MINUTE | 15 per client |
| ANALYSIS_TOTAL_PER_MINUTE | 120 aggregate |

Render supplies PORT. Missing CLASSROOM_DEMO_CODE fails closed for AI while data, analysis and rule hints remain available. There is no draft-body or classroom-code logging.

The in-memory limiter is for one process and one instance. Counters reset on restart. Keep one uvicorn worker; use shared storage and a durable budget policy if scaling. If client addresses are indistinguishable behind a proxy, per-client limits conservatively apply to that shared address. Aggregate limits apply independently. CORS is a browser-origin control; the code gate and server limits protect the AI endpoint separately.

AI input: maximum 1,500 characters for the sentence, 200 for audience, 300 for purpose; request body capped at 8 KiB. Analyse keeps its original 20,000-character limit with a 100 KB body cap. Rejections use 401/413/422/429/503 as appropriate; 429 includes Retry-After.

## Configure the actual backend

First verify the actual Render HTTPS /healthz, /api/data and /api/analyse after a successful deploy. Then run:

```sh
python scripts/configure_frontend.py --backend https://ACTUAL-SERVICE-HOST
```

Replace the placeholder with Render's real returned origin. This writes only the public URL into docs/config.js. Commit and push it before enabling Pages. No secret is written to that file. `starter/static/config.js` independently retains the same-origin local preview.

Only the selected sentence, audience, purpose, focus and Python-computed sentence metrics go to the gateway. The browser sends the classroom code to the backend in X-Classroom-Code. The code stays in the page input and is excluded from saved drafts and exports. The model explains and suggests; it never replaces computed metrics.

## GitHub Pages

Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main → Folder: /docs → Save. Use the actual URL reported by GitHub after deployment. All static paths are relative and support /repository-name/.

Changing a user-site repository to /docs changes what its root site shows. Use a separate project repository to preserve an existing personal homepage.

On the actual public URL verify separately:
1. W2 loads with its correct audience and purpose.
2. Analyse gives 248 words, 20 sentences, TTR 0.665 and four limited-rule matches.
3. A quoted rule hint matches the focus; an example appears only when requested.
4. Missing/wrong code cannot invoke AI; correct code produces a validated live reply labelled AI 提示 / gpt-6.1-sol.
5. Save the original, revise and reanalyse; baseline stays unchanged. Save a reflection and export both profiles.
6. Browser requests target the actual Render HTTPS origin with no CORS/mixed-content errors. Check 390px width.

Unconfigured/unavailable services show clear status. Public fallback samples can load without Python, but new metrics need the backend. Rule hints remain explicitly labelled. Local previews and mocked responses do not prove public deployment.

Official references:
- https://render.com/docs/deploy-fastapi
- https://render.com/docs/python-version
- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
