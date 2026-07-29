# manim-lab

Turn a text prompt into a short explainer video, in the style of 3Blue1Brown,
with one command:

```bash
python make_video.py "explain binary search"
# -> out/binary_search.mp4
```

Gemini plans the video as a sequence of scenes, writes Manim code for each
scene, Docker renders each scene to an MP4, and ffmpeg stitches them together.

---

## How it works (architecture)

```
user prompt
   │
   ▼
Stage A — planner.py    prompt        -> structured JSON scene plan      (Gemini)
   │
   ▼
Stage B — codegen.py    each scene    -> standalone Manim Python file    (Gemini, parallel)
   │
   ▼
Render  — renderer.py   each .py      -> per-scene MP4 via Docker        (parallel, LLM repair on failure)
   │
   ▼
Stitch  — stitch.py     per-scene MP4 -> final MP4 via ffmpeg concat
```

### Modules

| File | Responsibility |
|---|---|
| `pipeline/config.py` | Constants: model names, quality flag, retry/timeout limits, scene count/duration bounds, paths. |
| `pipeline/llm.py` | Thin wrapper around the Gemini SDK. Everything else calls `generate()`, never the SDK directly. Handles retry-with-backoff on 429/5xx and strips markdown code fences from model output. |
| `pipeline/planner.py` | Stage A. `make_plan(prompt)` turns a prompt into a validated JSON scene plan (title, slug, list of scenes with goal/visuals/narration/duration). Validates the plan and does one repair pass on failure before raising `PlanError`. |
| `pipeline/codegen.py` | Stage B. `generate_all_scenes(plan)` turns each scene into a standalone Manim `Scene{id}` class, running one LLM call per scene **concurrently**. `sanitize()` enforces the output is safe (only `from manim import *`, no dangerous builtins, correct class name) before it ever reaches Docker. |
| `pipeline/renderer.py` | `render_all(sources, quality)` renders each scene's `.py` file inside the `manimcommunity/manim` Docker container, **concurrently** (capped at 4 workers). On a render failure, sends the error back to Gemini for a one-shot code repair and retries, up to `MAX_RENDER_ATTEMPTS`. A scene that never recovers is dropped (not fatal) unless `--strict` is passed. |
| `pipeline/stitch.py` | Concatenates the per-scene clips into the final video with `ffmpeg -c copy` (instant, no re-encode), falling back to an `libx264` re-encode if the clips aren't stream-compatible. |
| `make_video.py` | CLI entrypoint. Wires the four stages together, times each one, prints a breakdown, and cleans up `work/` when done. |
| `prompts/planner_system.md`, `prompts/codegen_system.md`, `prompts/few_shot_scenes.py` | The system prompts (and few-shot example scenes) that drive Stage A and Stage B. `codegen_system.md` in particular is the single most important file for output quality — see the comments in `IMPLEMENTATION_PLAN.md` if you're tuning it. |

### Design decisions that matter

- **The Gemini API key never enters the Docker container.** Only the host
  Python process talks to Gemini — the container renders untrusted generated
  code and has no credentials.
- **Everything that can run in parallel does.** Per-scene codegen calls and
  per-scene renders both run concurrently (`ThreadPoolExecutor`), because LLM
  latency and render time both add up fast otherwise.
- **Generated code is sanitized before it's trusted.** `codegen.sanitize()`
  rejects unexpected imports and dangerous tokens (`subprocess`, `eval(`,
  `open(`, etc.) on the host, before a render is even attempted. Docker is
  still the real sandbox boundary — this just avoids wasting a render cycle
  on obviously bad output.
- **This is local software.** No deployment, database, or auth beyond what's
  described below — see `IMPLEMENTATION_PLAN.md` for what's explicitly out
  of scope for the core pipeline.

---

## Setup

### Prerequisites

- **Python 3.11+**
- **Node.js + npm** — only needed for the web demo's frontend (`frontend/`), not the CLI.
- **Docker Desktop**, running, with the `manimcommunity/manim` image pulled:
  ```bash
  docker pull manimcommunity/manim
  ```
  **On Windows**, Docker Desktop requires WSL2. If `docker` commands hang or
  fail with a "cannot connect to the Docker daemon" / named-pipe error, WSL2
  probably isn't installed yet:
  ```bash
  wsl --install
  ```
  This needs an elevated (Administrator) terminal and ends with a reboot.
  After rebooting, start Docker Desktop and give it a few seconds to finish
  initializing before retrying.
- **ffmpeg** on the host (used for the final stitch step — this particular
  `manimcommunity/manim` image build doesn't include an `ffmpeg` binary):
  ```bash
  # macOS
  brew install ffmpeg
  # Windows
  winget install Gyan.FFmpeg
  # Linux (Debian/Ubuntu)
  sudo apt install ffmpeg
  ```
  On Windows, a fresh PATH change from an installer often doesn't apply to
  an already-open terminal — open a new terminal (or restart your IDE/shell)
  before verifying `ffmpeg` is found.
- **A Gemini API key** — get one at [aistudio.google.com](https://aistudio.google.com/apikey).
  The free tier caps at 20 requests/day for the flash model this pipeline
  uses (`gemini-flash-latest`, see `pipeline/config.py`), which this
  pipeline's parallel LLM calls can burn through in a single run — a paid
  tier is recommended for anything beyond light testing. Use `--mock` /
  `MOCK_LLM=1` (see below) to try things out without spending quota.

### Install

```bash
git clone <this-repo>
cd manim-lab
python3 -m venv .venv
pip install -r requirements.txt
```

Activate the venv (optional but recommended) before the `pip install` above:

```bash
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your-key-here
```

### Verify the setup

```bash
# Docker + Manim render a sample scene (bash / PowerShell):
docker run --rm -v "$(pwd):/manim" manimcommunity/manim manim -qm example.py SquareToCircle
# cmd.exe doesn't support $(...) — use this instead:
docker run --rm -v "%cd%:/manim" manimcommunity/manim manim -qm example.py SquareToCircle

# Gemini API key works:
python3 -c "from pipeline.llm import generate; print(generate('Be terse.', 'Say hi', 'gemini-flash-latest'))"
```

If both of those work, you're ready to go.

---

## Usage

```bash
python make_video.py "explain binary search"
python make_video.py "explain the derivative" --quality qh
python make_video.py "explain recursion" --scenes 3 --keep-work --strict
```

| Flag | Default | Meaning |
|---|---|---|
| `prompt` (positional) | — | What to explain. |
| `--quality {ql,qm,qh}` | `qm` | Render quality: `ql`=480p15, `qm`=720p30, `qh`=1080p60. Resolution is cheap — it's not usually the bottleneck. |
| `--scenes N` | — | Hint the planner to aim for about `N` scenes (still bounded to 3–6 overall). |
| `--keep-work` | off | Don't delete `work/` (the generated `.py` files and per-scene clips) after the run — useful for debugging a specific scene. |
| `--strict` | off | Fail the whole run if any scene can't be rendered, instead of dropping it and continuing with the rest. |
| `--sequential` | off | Debug flag: disable parallelism in codegen/render, to compare timing against the normal concurrent run. |
| `--mock` | off | Skip Gemini calls entirely, using canned-but-valid output instead (`pipeline/mock_llm.py`). Docker render and ffmpeg stitch still run for real. Useful for testing the pipeline without spending API quota — same effect as setting `MOCK_LLM=1`. |

The finished video is written to `out/{slug}.mp4`, where `slug` comes from
the plan (e.g. `out/binary_search.mp4`).

Every run — success or failure — ends with a timing breakdown:

```
plan          3.1s
codegen       8.4s   (5 scenes, parallel)
render       41.2s   (5/5 scenes, parallel)
stitch        0.3s
─────────────────
total        53.0s
```

## Web demo

A Flask + React demo built on the same pipeline: a mock SCHD (dividend ETF)
fund page with a floating widget that generates a base explainer video plus
3 LLM-suggested "what if" variants (each grounded in a real number from the
page — e.g. its actual expense ratio), which you can click between instantly
since they're all pre-generated. A free-text box lets you ask your own
follow-up, generated live on demand.

```bash
# Backend (from the project root, needs the same .env/Docker/ffmpeg setup as the CLI)
python server.py
# -> http://localhost:5000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# -> http://localhost:5173
```

Set `MOCK_LLM=1` before `python server.py` to try the whole flow without
spending Gemini quota (a session generates 4+ videos' worth of calls) — the
SCHD demo's 4 topics use real, hand-written content either way
(`pipeline/schd_content.py`), so this mode is safe to demo with:

```bash
# bash
MOCK_LLM=1 python server.py
# PowerShell
$env:MOCK_LLM = "1"; python server.py
# cmd.exe
set MOCK_LLM=1 && python server.py
```

This is local-only for now — no cloud deployment yet.

## Running the tests

```bash
python3 -m pytest
```

All pipeline logic is covered with the LLM/Docker/ffmpeg calls mocked, so the
suite runs in under a second with no API key, Docker, or network required.

## Known limitations

- **Gemini free-tier quota**: 20 requests/day is easy to exhaust in one real
  run, because codegen fires one concurrent request per scene — and a web
  demo session generates 4+ full videos at once. Use `--mock`/`MOCK_LLM=1`
  for iteration; live testing is realistically limited to a handful of runs
  per day on the free tier.
- **ffmpeg is a host dependency**, not a zero-dependency Docker-only step —
  the `manimcommunity/manim` image doesn't ship an `ffmpeg` binary (it renders
  via PyAV bindings internally instead).
- **The web demo is local-only** — no cloud deployment, persistence, or
  auth. TTS/narration audio and non-Gemini provider support also aren't
  implemented — see `IMPLEMENTATION_PLAN.md` for what was deliberately out
  of scope for the core pipeline's initial build.
