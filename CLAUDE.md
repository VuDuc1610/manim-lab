# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

manim-lab turns a text prompt into a short 3Blue1Brown-style explainer video. Gemini plans a scene-by-scene JSON structure, Gemini writes standalone Manim code per scene, Docker renders each scene to an MP4, and ffmpeg stitches them together. There are two entry points onto the same pipeline:

- **CLI** (`make_video.py`) — one-shot, synchronous, `prompt -> out/{slug}.mp4`.
- **Web demo** (`server.py` + `webapp/`) — a Flask backend + Vite/React frontend (`frontend/`) built around a specific demo: a mock SCHD fund page with a floating widget that generates a base explainer video plus 3 LLM-suggested "what if" variants concurrently, and a free-text follow-up that generates on demand. See `webapp/orchestrator.py`'s docstring for why concurrent video generation needs a lock.

## Commands

```bash
# Backend setup
pip install -r requirements.txt

# Run the full test suite (fully mocked — no API key, Docker, or network needed)
python -m pytest

# Run a single test file / single test
python -m pytest tests/test_planner.py -q
python -m pytest tests/test_planner.py::test_make_plan_repairs_invalid_json_then_succeeds -q

# CLI
python make_video.py "explain binary search"
python make_video.py "explain recursion" --scenes 3 --keep-work --strict
python make_video.py "explain binary search" --mock   # no Gemini calls, see below

# Web demo backend (Flask on :5000)
python server.py

# Web demo frontend (Vite on :5173, separate terminal)
cd frontend && npm install && npm run dev
```

Verify the environment is set up correctly:
```bash
docker run --rm -v "$(pwd):/manim" manimcommunity/manim manim -qm example.py SquareToCircle
python3 -c "from pipeline.llm import generate; print(generate('Be terse.', 'Say hi', 'gemini-2.5-flash'))"
```

### Mock mode — develop without spending Gemini quota

Gemini's free tier is 20 requests/day, easily exhausted by one real run (one call per scene, times however many scenes, times however many videos). Set `MOCK_LLM=1` (or pass `--mock` to `make_video.py`) to swap every `pipeline.llm.generate()` call for canned-but-schema-valid output from `pipeline/mock_llm.py`. Docker render and ffmpeg stitch still run for real — only the Gemini calls are skipped. Useful failure-injection env vars for exercising retry paths are documented in `pipeline/mock_llm.py`'s module docstring (`MOCK_LLM_FAIL_PLAN`, `MOCK_LLM_FAIL_RENDER`, `MOCK_LLM_ALWAYS_FAIL_RENDER`, `MOCK_LLM_FAIL_DECODE`).

## Architecture

### Pipeline stages (`pipeline/`)

Both entry points call the same stage functions in the same order:

1. **`decode.py`** (web-only, `decode_fund_content`) — turns raw fund-page text into a topic prompt plus 3 suggested "what if" variants, each grounded in a real number from the input. Feeds into stage 2 below just like a CLI prompt would.
2. **`planner.py`** (`make_plan`) — one Gemini call turns a topic prompt into a validated JSON scene plan (`title`, `slug`, `scenes: [{id, goal, visuals, narration, duration_sec}]`). One repair retry on validation failure before raising `PlanError`.
3. **`codegen.py`** (`generate_all_scenes`) — one Gemini call *per scene*, concurrently, each producing a standalone `class Scene{id}(Scene)` Manim script. `sanitize()` rejects anything with imports other than `from manim import *` or dangerous tokens (`subprocess`, `eval(`, `open(`, etc.) before it's ever handed to Docker.
4. **`renderer.py`** (`render_all`) — renders each scene concurrently (capped at 4 workers) via `docker run manimcommunity/manim`. A render failure triggers one Gemini repair call and a retry, up to `MAX_RENDER_ATTEMPTS`; a scene that never recovers is dropped unless `strict=True`.
5. **`stitch.py`** (`stitch`) — `ffmpeg -c copy` concat, falling back to a `libx264` re-encode if the clips aren't stream-compatible.

`pipeline/llm.py`'s `generate(system, user, model)` is the **single chokepoint** for every Gemini call — nothing else touches the SDK directly, and `MOCK_LLM` is checked exactly once, at the top of that function.

### Why Docker

The `manimcommunity/manim` container renders untrusted LLM-generated code and never receives the Gemini API key — only the host process holds credentials. `codegen.sanitize()` is a cheap pre-filter on the host to avoid wasting a render cycle on obviously bad output; Docker is the actual sandbox boundary.

### Web orchestration layer (`webapp/`)

`orchestrator.py` calls the exact same pipeline functions the CLI uses, just multiple times per session (base + 3 suggestions + optional follow-ups). This matters because `renderer.py` and `stitch.py` write to **fixed, scene-id-only paths** (`work/scene_{id}.py`, `media/videos/scene_{id}/...`, `work/concat.txt`) with no per-video namespacing — running two whole-video pipelines' render+stitch steps at the same time would collide. `orchestrator.py`'s `_render_disk_lock` serializes exactly that portion across every concurrently-running video; `make_plan()`/`generate_all_scenes()` (pure Gemini calls, no shared disk state) stay fully concurrent. Do not "fix" this by touching `renderer.py`/`stitch.py` — the lock at the orchestration layer is the intended design.

`jobs.py` is an in-memory session/video store (dataclasses + a `threading.Lock`, no DB) — appropriate for this single-local-user demo, not meant to be durable.

The webapp is a long-lived process, unlike the CLI's one-shot invocation — `pipeline/config.py` only creates `work/`/`out/` once at import time, so `orchestrator._run_video_pipeline` defensively re-asserts both directories exist before every render.

### Windows encoding gotchas

This has been developed/tested on Windows, where the default console/subprocess encoding is cp1252, not UTF-8. `make_video.py` and `server.py` force `sys.stdout`/`sys.stderr` to UTF-8 on startup; `renderer.py`'s Docker subprocess call and `stitch.py`'s ffmpeg subprocess call both pass `encoding="utf-8", errors="replace"` explicitly. If you add another `subprocess.run(..., text=True)` call anywhere in this codebase, it needs the same treatment or it will crash on non-ASCII output.

### Frontend (`frontend/`)

Vite + React, talks to the Flask backend via `src/api.js` (absolute `http://localhost:5000` base URL, CORS-enabled on the Flask side rather than a Vite proxy). Two things worth knowing if touching video playback: cross-origin `<video src>` needs a `Cross-Origin-Resource-Policy` header or Chromium's ORB blocks it (`flask-cors`'s `Access-Control-Allow-Origin` alone doesn't cover a native `<video>` resource load); `VideoPlayer.jsx` fetches the video and plays it from a blob URL rather than pointing `<video src>` directly at the cross-origin URL, since direct Range-request loading was unreliable in testing.
