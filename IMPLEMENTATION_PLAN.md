# Implementation Plan — Text-to-Manim Video Generator

This document is the spec for building the core pipeline. Work through the tasks in
order. Each task has acceptance criteria — do not move to the next task until the
current one passes.

---

## 0. Context

**Goal:** a single command turns a text prompt into an explainer video.

```bash
python make_video.py "explain binary search"
# -> out/binary_search.mp4  in under ~90 seconds
```

**What already exists (do not rebuild):**

- Docker is installed and `manimcommunity/manim` image is pulled and verified working.
  This command renders successfully from the project root:
  ```bash
  docker run --rm -v "$(pwd):/manim" manimcommunity/manim manim -qm example.py SquareToCircle
  ```
- `.env` exists at project root containing `GEMINI_API_KEY=...`
- `.gitignore` already ignores `.env`, `media/`, `__pycache__/`
- Packages installed: `google-genai`, `python-dotenv`

**Pipeline shape:**

```
user prompt
   -> Stage A (LLM)  : prompt        -> structured JSON scene plan
   -> Stage B (LLM)  : each scene    -> standalone Manim Python file   [parallel]
   -> Render         : each .py      -> per-scene MP4 via Docker       [parallel]
                                        with an LLM repair loop on failure
   -> Stitch         : per-scene MP4 -> final MP4 via ffmpeg concat
```

---

## 1. Hard constraints

These are not negotiable. Violating them breaks the design.

1. **The API key never enters the container.** Only the host Python process talks to
   Gemini. The container renders untrusted generated code and must have no
   credentials. Do not pass `-e GEMINI_API_KEY` to `docker run`, ever.
2. **Design for Gemini Flash, not Pro.** Free-tier Pro has a very low daily request
   cap. Default model is `gemini-2.5-flash`. Make the model an easily-changed
   constant in one place.
3. **No web server, no database, no UI, no auth, no queue.** This phase is a local
   CLI only. Those come later and adding them now will make the core harder to tune.
4. **No text-to-speech / narration audio yet.** The plan JSON carries a `narration`
   field so it is ready later, but nothing consumes it in this phase.
5. **Use the default Cairo renderer.** Do not add `--renderer=opengl`. It is faster
   but has feature gaps that will waste debugging time.
6. **Everything that can run in parallel must run in parallel.** Per-scene LLM calls
   and per-scene renders are independent. Sequential execution will blow the time
   budget.

---

## 2. Target file layout

```
manim-lab/
├── .env                        # exists
├── .gitignore                  # exists
├── make_video.py               # CLI entrypoint
├── pipeline/
│   ├── __init__.py
│   ├── config.py               # constants, paths, model names
│   ├── llm.py                  # Gemini wrapper + retry + fence stripping
│   ├── planner.py              # Stage A
│   ├── codegen.py              # Stage B
│   ├── renderer.py             # Docker render + repair loop
│   └── stitch.py               # ffmpeg concat
├── prompts/
│   ├── planner_system.md
│   ├── codegen_system.md
│   └── few_shot_scenes.py      # reference scenes, injected into codegen prompt
├── work/                       # scratch, gitignored: generated .py + per-scene mp4
└── out/                        # final videos
```

Add `work/` and `out/` to `.gitignore`.

---

## Task 1 — `pipeline/config.py` and `pipeline/llm.py`

### config.py

Plain module-level constants. No classes needed.

- `PLANNER_MODEL = "gemini-2.5-flash"`
- `CODEGEN_MODEL = "gemini-2.5-flash"`
- `REPAIR_MODEL = "gemini-2.5-flash"`
- `DEFAULT_QUALITY = "-qm"` (720p30)
- `MAX_RENDER_ATTEMPTS = 3`
- `RENDER_TIMEOUT_SEC = 180`
- `MIN_SCENES = 3`, `MAX_SCENES = 6`
- `MIN_SCENE_SEC = 5`, `MAX_SCENE_SEC = 10`
- Path constants for `WORK_DIR`, `OUT_DIR`, `PROMPTS_DIR`, and a `PROJECT_ROOT`

Create `work/` and `out/` at import time if missing.

### llm.py

One thin wrapper. Everything else in the codebase calls this, never the SDK directly.

```python
def generate(system: str, user: str, model: str) -> str:
    """Single-turn call. Returns raw text."""
```

Requirements:

- Load `.env` via `python-dotenv`, read `GEMINI_API_KEY`, construct one module-level
  `genai.Client`. Fail fast with a clear message if the key is missing.
- Pass `system` via the SDK's system-instruction config, not by prepending to `user`.
- **Retry on 429 with exponential backoff:** 1s, 2s, 4s, 8s, then give up. Free tier
  rate limits are low and you will hit them constantly while iterating. Log each
  retry to stderr so the delay is visible rather than looking like a hang.
- Retry on transient 5xx the same way. Do not retry on 400 — that is a bug in the
  request, surface it immediately.

Also expose a helper used by both stages:

```python
def strip_code_fences(text: str) -> str:
    """Remove leading ```python / ``` and trailing ``` if present."""
```

Models add fences even when told not to. Strip defensively rather than relying on
the prompt.

### Acceptance criteria

- `python -c "from pipeline.llm import generate; print(generate('Be terse.', 'Say hi', 'gemini-2.5-flash'))"`
  prints a short response.
- Missing key produces a readable error, not a `KeyError` traceback.
- `strip_code_fences` is unit-tested against: fenced with language tag, fenced
  without tag, unfenced, and fence-in-the-middle (should be left alone).

---

## Task 2 — Stage A: `pipeline/planner.py`

Turns the user's prompt into a validated scene plan.

### Contract

```python
def make_plan(user_prompt: str) -> dict:
    """Returns a validated plan dict. Raises PlanError after retries."""
```

### Output schema

```json
{
  "title": "How binary search works",
  "slug": "binary_search",
  "scenes": [
    {
      "id": 1,
      "goal": "Show a sorted array of 16 numbers",
      "visuals": ["16 squares in a row with values", "index labels below each"],
      "narration": "Here's a sorted list of numbers.",
      "duration_sec": 6
    }
  ]
}
```

`slug` must be lowercase, alphanumeric plus underscores — it names the output file.

### Validation

Write `validate_plan(plan) -> list[str]` returning a list of problems. Check:

- `title` and `slug` are non-empty strings; `slug` matches `^[a-z0-9_]+$`
- `scenes` length is between `MIN_SCENES` and `MAX_SCENES`
- `id` values are exactly `1..n`, sequential, no gaps
- each `duration_sec` is between `MIN_SCENE_SEC` and `MAX_SCENE_SEC`
- `goal` and `narration` are non-empty; `visuals` is a non-empty list of strings

### Retry behaviour

If JSON parsing fails or validation returns problems, make **one** repair call
including the specific problems in the message, then re-validate. If it fails twice,
raise `PlanError` with the raw response attached for debugging.

### System prompt — `prompts/planner_system.md`

Write it to cover:

- Role: plan a short explainer video in the style of 3Blue1Brown.
- Style rules: build intuition before formalism; open with something concrete and
  visual, not a definition; exactly one idea per scene; each scene should visually
  build on the previous one rather than starting fresh.
- Every scene must be expressible with geometric primitives — shapes, arrows, text,
  graphs, number lines, coordinate planes. Never plan a visual that needs a
  photograph, an illustration of a real object, or an organic form.
- Hard limits: between MIN and MAX scenes, each 5-10 seconds.
- Output rules: return only a JSON object, no prose, no markdown fences.

Include one complete worked example (input prompt -> full JSON output) at the end of
the prompt file. It disambiguates the schema better than the schema description does.

### Acceptance criteria

- Three different prompts — one mathematical ("explain the derivative"), one CS
  ("explain binary search"), one non-technical ("explain supply and demand") — all
  produce plans that pass validation on the first or second attempt.
- Deliberately corrupting the model output (monkeypatch `generate` to return junk)
  triggers the repair path and then raises `PlanError` cleanly.

---

## Task 3 — Stage B: `pipeline/codegen.py`

Turns each scene of the plan into a standalone Manim file.

### Contract

```python
def generate_scene_code(plan: dict, scene: dict) -> str:
    """Returns Python source for one scene."""

def generate_all_scenes(plan: dict) -> dict[int, str]:
    """scene id -> source. Runs concurrently."""
```

Use `ThreadPoolExecutor` with `max_workers=len(scenes)`. These are I/O-bound network
calls, threads are fine — do not reach for asyncio.

Pass the **whole plan plus the target scene** into each call, not just the scene. The
model needs to know what came before to keep the visuals continuous, and knowing
what comes after prevents it from cramming everything into scene 1.

### Class naming

Generated class must be named exactly `Scene1`, `Scene2`, ... matching the scene `id`.
The renderer builds its command from this, so it must be predictable.

### Post-generation sanitizing

After `strip_code_fences`, run `sanitize(code, scene_id) -> str` which:

1. Asserts `class Scene{id}(Scene):` appears in the source. If not, raise — do not
   attempt to rename it, regenerate instead.
2. Asserts the only import is `from manim import *`. Reject any other `import`
   statement. This is both a safety check and a strong signal the model went
   off-script.
3. Rejects the tokens `subprocess`, `eval(`, `exec(`, `__import__`, `open(`,
   `socket`, `requests`. The container is the real sandbox, but catching this on the
   host saves a wasted render cycle.
4. Emits a **warning** (not an error) if `MathTex` or `Tex` appears more than twice
   in a single scene — see the performance notes in Task 6.

### System prompt — `prompts/codegen_system.md`

This prompt is the single highest-leverage file in the project. Expect to iterate on
it more than any code. It must contain:

**Output format rules**
- Emit only Python source. No markdown fences, no commentary, no explanation.
- Exactly one import line: `from manim import *`
- Exactly one class, named `Scene{id}`, subclassing `Scene`.
- All logic inside `construct(self)`.

**Layout rules — these matter more than anything else**
- No two mobjects may visually overlap at any point.
- Position with `.next_to()`, `.to_edge()`, `.arrange()`, `.shift()` relative to
  other objects. Avoid absolute coordinates except for a deliberate anchor.
- Everything must stay inside the frame: x within -7 to 7, y within -4 to 4.
- Before introducing a new group of objects, `FadeOut` what is no longer needed.
- End every scene with `self.wait(1)`.
- Font sizes: titles 40-48, body text 28-32, labels 20-24. Never leave the default
  when text sits next to other text.
- If more than four text objects are on screen, use `VGroup(...).arrange(DOWN, buff=0.5)`
  rather than positioning each one.

**Content rules**
- Use `Text` for all words and labels. Use `MathTex` **only** for genuine
  mathematical notation that cannot be written as plain text. This is a hard
  performance rule, not a style preference.
- Total animation time must be close to the scene's `duration_sec`.
- Reuse colors consistently: one accent color for the object under discussion,
  muted gray for context.

**Few-shot examples**
Include 2-3 complete, correct scenes inline at the end of the prompt, loaded from
`prompts/few_shot_scenes.py`. Make one of them a scene with several labeled elements
arranged in a row, since that layout is where the model fails most often. The
examples anchor style far more effectively than the instructions do.

### Acceptance criteria

- For a valid plan, every scene returns source that passes `sanitize`.
- Generating a 4-scene plan takes roughly as long as generating one scene, not four
  times as long. Verify parallelism actually works — log wall-clock time.

---

## Task 4 — Render + repair: `pipeline/renderer.py`

### Contract

```python
def render_scene(code: str, scene_id: int, quality: str) -> Path:
    """Writes source, renders, repairs and retries on failure. Returns MP4 path."""

def render_all(sources: dict[int, str], quality: str) -> dict[int, Path]:
    """Renders every scene concurrently."""
```

### Render call

Write source to `work/scene_{id}.py`, then:

```python
subprocess.run(
    ["docker", "run", "--rm",
     "-v", f"{PROJECT_ROOT}:/manim",
     "manimcommunity/manim",
     "manim", quality, f"work/scene_{scene_id}.py", f"Scene{scene_id}"],
    capture_output=True, text=True, timeout=RENDER_TIMEOUT_SEC,
)
```

Notes:

- Mount the **project root**, not `work/`, and give Manim the relative path. Manim
  writes output under `media/` relative to its working directory, which keeps all
  artifacts in one predictable place.
- `timeout` is mandatory. A pathological scene can spin indefinitely and will hang
  the whole run. Treat `TimeoutExpired` as a render failure and feed
  `"Render exceeded {N}s — the scene is too complex, simplify it drastically"` to
  the repair step.
- Do not pass `-p`. There is no video player in the container.
- Do not pass `--disable_caching`. Caching is harmless here.

### Locating the output

Manim writes to `media/videos/scene_{id}/{resolution}/Scene{id}.mp4` where resolution
depends on the quality flag (`-qm` -> `720p30`, `-qh` -> `1080p60`, `-ql` -> `480p15`).
Rather than hardcoding that mapping, glob for `media/videos/scene_{id}/**/Scene{id}.mp4`
and take the most recently modified match. It is more robust across Manim versions.

### Repair loop

On non-zero exit:

1. If `attempt >= MAX_RENDER_ATTEMPTS`, raise `RenderError`.
2. Extract the **last 30 lines** of stderr only. Full Manim tracebacks are enormous
   and mostly framework frames; sending the whole thing wastes tokens and buries the
   actual error.
3. Call the LLM with the broken source and that error excerpt. The repair prompt
   should instruct: return the complete corrected file, change as little as possible,
   do not explain.
4. Re-run `sanitize`, then retry.

Log each attempt clearly: `[scene 2] attempt 2/3 — NameError: name 'Arrow3D' is not defined`.
You will be reading these logs constantly while tuning prompts.

### Parallelism

`render_all` uses `ThreadPoolExecutor`. Cap `max_workers` at `min(len(scenes), 4)` —
each container is CPU-hungry and oversubscribing makes everything slower.

If one scene exhausts its retries, do not kill the whole run by default. Log it, drop
that scene, and continue with the rest — a 3-scene video beats no video during a demo.
Add a `--strict` flag that fails hard instead, for when you are debugging.

### Acceptance criteria

- A scene with a deliberate error (reference an undefined class) gets repaired and
  renders successfully.
- A scene with an unfixable error fails after exactly 3 attempts with a clear message.
- Four scenes render in roughly the time of the slowest one, not the sum.

---

## Task 5 — Stitch: `pipeline/stitch.py`

### Contract

```python
def stitch(clips: list[Path], out_path: Path) -> Path:
```

Use ffmpeg's concat demuxer:

1. Write `work/concat.txt` with one `file '<absolute path>'` line per clip, ordered
   by scene id.
2. Run `ffmpeg -y -f concat -safe 0 -i work/concat.txt -c copy out/{slug}.mp4`.

`-c copy` avoids re-encoding and is nearly instant, but it **requires every clip to
share resolution, framerate, and codec**. That holds as long as all scenes render
with the same quality flag — enforce that in `make_video.py` rather than trusting it.

Add a fallback: if `-c copy` fails, re-run with `-c:v libx264 -pix_fmt yuv420p` and
log that a re-encode was needed.

Use the ffmpeg inside the Docker image rather than requiring a host install:

```bash
docker run --rm -v "$(pwd):/manim" --entrypoint ffmpeg manimcommunity/manim ...
```

This keeps host dependencies at zero. Paths inside the concat file must then be
container paths (`/manim/...`), so generate them accordingly.

### Acceptance criteria

- Four clips concatenate into one MP4 whose duration is the sum of the parts.
- The output plays in QuickTime without a re-encode warning.

---

## Task 6 — CLI and performance instrumentation

### `make_video.py`

```bash
python make_video.py "explain binary search"
python make_video.py "explain the derivative" --quality qh
python make_video.py "explain recursion" --scenes 3 --keep-work --strict
```

Arguments:

- positional `prompt`
- `--quality` one of `ql|qm|qh`, default `qm`, mapped to the `-q*` flag
- `--scenes` optional integer hint passed into the planner prompt
- `--keep-work` skip cleanup of `work/`
- `--strict` fail the run if any scene fails to render

### Timing instrumentation — required, not optional

Print a timing breakdown at the end of every run:

```
plan          3.1s
codegen       8.4s   (4 scenes, parallel)
render       41.2s   (4 scenes, parallel, 1 repair)
stitch        0.3s
─────────────────
total        53.0s
```

This is the whole point of the phase. You cannot tune what you cannot see, and the
intuition about where time goes is usually wrong — LLM latency frequently exceeds
render time on short videos.

### Performance rules to bake in

1. **Resolution is cheap.** `-qm` to `-qh` costs roughly 30-40% more render time. It
   is not the bottleneck; do not optimize here first.
2. **LaTeX is expensive.** `MathTex` and `Tex` shell out to a LaTeX compiler and can
   take seconds *per object*. `Text` and `MarkupText` use Pango and are close to
   instant. A scene with ten `MathTex` labels can be an order of magnitude slower
   than the same scene using `Text`. The codegen prompt rule and the `sanitize`
   warning both exist to enforce this — if the timing report shows render dominating,
   check the MathTex count first.
3. **Parallelism is the biggest lever.** Verify it is actually happening by comparing
   the parallel timing against a `--sequential` debug flag.
4. **Scene count and duration drive everything.** If runs are too slow, cutting from
   6 scenes to 4 beats any micro-optimization.

### Acceptance criteria

- `python make_video.py "explain binary search"` produces `out/binary_search.mp4`
  in under 90 seconds at `-qm`.
- The timing report prints on both success and failure.
- Re-running the same prompt twice produces two working videos (no stale-state bugs
  from `work/`).

---

## 3. Test inputs

Keep these three as the standing regression set. Run all three after any prompt change:

1. `"explain binary search"` — CS, sequential steps, array visuals
2. `"explain what a derivative is"` — math, needs graphs and real MathTex
3. `"explain supply and demand"` — non-math, tests that the system is not
   accidentally math-only

For each, check: does it render without repair, does any text overlap, does anything
run off-frame, is each scene readable at the length it is on screen.

---

## 4. Explicitly out of scope for this phase

Do not build these even if they seem easy:

- Web UI, API server, job queue, database
- Narration audio / TTS
- User accounts, history, persistence
- Streaming progress to a frontend
- Prompt caching or a template library
- Any non-Gemini provider (a Groq fallback comes later)

The next phase is architecture. Getting there requires a fast, reliable local loop
first — that is all this document covers.
