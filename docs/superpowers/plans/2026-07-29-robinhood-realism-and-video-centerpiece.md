# Robinhood Realism + AI Video Centerpiece — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the demo's fund page feel like a real Robinhood screen, and make AI video generation the page's centerpiece (inline, always-visible, on-demand suggestions, real progress) instead of a floating popup — without breaking the existing pipeline/orchestrator/API contract along the way.

**Architecture:** Two independent-but-sequenced efforts. Phase 1 is a frontend-only visual/terminology pass (zero backend risk). Phases 2–3 redesign the video experience: Phase 2 changes the backend contract so suggestion videos become on-demand instead of auto-generated, verified via the existing mocked pytest suite before any UI touches it; Phase 3 replaces the floating-button/popup UI with an inline module built against that new contract. Phase 4 is a cohesion pass.

**Tech Stack:** Flask + in-memory dataclass store (`webapp/`), Gemini + Docker + ffmpeg pipeline (`pipeline/`, untouched by this plan), Vite + React frontend (`frontend/`, no test runner — `oxlint` + `vite build` + manual browser checks are the verification tools).

## Global Constraints

- Never touch `pipeline/renderer.py` or `pipeline/stitch.py`'s locking/path design — `webapp/orchestrator.py`'s `_render_disk_lock` is the intended fix for their shared fixed-path writes; do not "fix" this elsewhere (see `orchestrator.py`'s module docstring).
- `pipeline/llm.py`'s `generate()` stays the only chokepoint for Gemini calls — this plan adds no new LLM call sites.
- The API key must never reach the Docker container — this plan doesn't touch Docker invocation at all.
- Frontend has no test framework installed (checked `frontend/package.json` — only `oxlint`/`vite build`/`vite dev`). Frontend task verification = `npm run lint`, `npm run build`, and a manual check via `npm run dev`. Do not introduce a test framework as a side effect of this plan.
- Backend verification = `python -m pytest` (fully mocked, no API key/Docker/network needed per CLAUDE.md).
- Run `python server.py` (port 5000) and `cd frontend && npm run dev` (port 5173) together for manual checks.

---

## Phase 1 — Robinhood realism pass (frontend-only, zero backend risk)

The app already has a dark Robinhood-style theme, green accent, a basic app bar, and a price chart with range pills (see `frontend/src/index.css`, `App.jsx`, `PriceChart.jsx`) from a prior pass. This phase adds the pieces still missing: real app chrome, a decorative trade action, a watchlist toggle, a fuller/more realistic chart range set with data that actually changes per range, and a terminology/consistency cleanup.

### Task 1.1: Decorative trade action bar + toast feedback

**Files:**
- Create: `frontend/src/components/Toast.jsx`
- Create: `frontend/src/components/TradeBar.jsx`
- Modify: `frontend/src/pages/SchdFundPage.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: `<Toast message={string|null} onDone={() => void} />` — renders nothing if `message` is null, otherwise shows for 2.5s then calls `onDone`.
- Produces: `<TradeBar onAction={(label: string) => void} />` — renders "Buy" / "Sell" buttons, calls `onAction("Buy")` / `onAction("Sell")` on click.

- [ ] **Step 1: Write `Toast.jsx`**

```jsx
import { useEffect } from "react";

export default function Toast({ message, onDone }) {
  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(onDone, 2500);
    return () => clearTimeout(timer);
  }, [message, onDone]);

  if (!message) return null;
  return <div className="toast">{message}</div>;
}
```

- [ ] **Step 2: Write `TradeBar.jsx`**

```jsx
export default function TradeBar({ onAction }) {
  return (
    <div className="trade-bar">
      <button type="button" className="trade-button trade-sell" onClick={() => onAction("Sell")}>
        Sell
      </button>
      <button type="button" className="trade-button trade-buy" onClick={() => onAction("Buy")}>
        Buy
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Wire into `SchdFundPage.jsx`**

Add local state and render `TradeBar` + `Toast` at the bottom of the page, above the footer:

```jsx
import { useState } from "react";
import Toast from "../components/Toast";
import TradeBar from "../components/TradeBar";
// ...existing imports

export default function SchdFundPage() {
  const [toastMessage, setToastMessage] = useState(null);

  function handleTradeAction(label) {
    setToastMessage(`${label} isn't available in this demo`);
  }

  return (
    <div className="fund-page">
      {/* ...existing header/sections unchanged... */}
      <TradeBar onAction={handleTradeAction} />
      <footer className="fund-footer">Illustrative demo data, not live market data.</footer>
      <Toast message={toastMessage} onDone={() => setToastMessage(null)} />
    </div>
  );
}
```

- [ ] **Step 4: Add CSS** (append to `frontend/src/index.css`, following existing `--accent`/`--panel-bg-2`/`--danger` tokens)

```css
.trade-bar {
  display: flex;
  gap: 12px;
  margin: 24px 0;
  position: sticky;
  bottom: 16px;
}

.trade-button {
  flex: 1;
  border: none;
  border-radius: 14px;
  padding: 16px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.trade-button:active {
  transform: scale(0.98);
}

.trade-buy {
  background: var(--accent);
  color: var(--accent-contrast);
  box-shadow: var(--shadow-cta);
}

.trade-sell {
  background: var(--panel-bg-2);
  color: var(--text);
  border: 1px solid var(--border-strong);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  background: var(--panel-bg-2);
  border: 1px solid var(--border-strong);
  color: var(--text);
  padding: 12px 20px;
  border-radius: 999px;
  font-size: 13px;
  box-shadow: var(--shadow);
  z-index: 60;
}
```

- [ ] **Step 5: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual: `npm run dev`, click Buy/Sell, confirm the toast appears and disappears after ~2.5s.

```bash
git add frontend/src/components/Toast.jsx frontend/src/components/TradeBar.jsx frontend/src/pages/SchdFundPage.jsx frontend/src/index.css
git commit -m "feat: add decorative trade action bar with toast feedback"
```

### Task 1.2: Watchlist star toggle

**Files:**
- Create: `frontend/src/components/WatchlistStar.jsx`
- Modify: `frontend/src/pages/SchdFundPage.jsx` (render next to `VerifiedBadge` in `.fund-header-top`)
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: `<WatchlistStar />` — self-contained, local `useState` toggle, no props.

- [ ] **Step 1: Write `WatchlistStar.jsx`**

```jsx
import { useState } from "react";

export default function WatchlistStar() {
  const [watching, setWatching] = useState(false);

  return (
    <button
      type="button"
      className={`watchlist-star${watching ? " active" : ""}`}
      onClick={() => setWatching((w) => !w)}
      aria-label={watching ? "Remove from watchlist" : "Add to watchlist"}
      aria-pressed={watching}
    >
      {watching ? "★" : "☆"}
    </button>
  );
}
```

- [ ] **Step 2: Render it in `SchdFundPage.jsx`**, inside `.fund-header-top`, after `<VerifiedBadge />`:

```jsx
<div className="fund-header-top">
  <span className="fund-ticker">{schdFund.ticker}</span>
  <VerifiedBadge />
  <WatchlistStar />
</div>
```

- [ ] **Step 3: Add CSS**

```css
.watchlist-star {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 20px;
  cursor: pointer;
  line-height: 1;
  padding: 4px;
}

.watchlist-star.active {
  color: var(--accent);
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual: click the star, confirm it toggles filled/outline and turns green when active.

```bash
git add frontend/src/components/WatchlistStar.jsx frontend/src/pages/SchdFundPage.jsx frontend/src/index.css
git commit -m "feat: add watchlist star toggle to fund header"
```

### Task 1.3: Full Robinhood-style chart range set with per-range data

`PriceChart.jsx` currently has `RANGES = ["1D", "1W", "1M", "3M", "1Y", "ALL"]` and a single static `POINTS` array reused regardless of selected range (`frontend/src/components/PriceChart.jsx:7-24`). Real Robinhood uses `1D 1W 1M 3M YTD 1Y 5Y MAX`, and switching ranges visibly changes the line.

**Files:**
- Modify: `frontend/src/components/PriceChart.jsx`

- [ ] **Step 1: Replace the range list and add a per-range point generator**

```jsx
import { useMemo, useState } from "react";

const RANGES = ["1D", "1W", "1M", "3M", "YTD", "1Y", "5Y", "MAX"];

// Deterministic pseudo-random walk seeded by range name — illustrative only
// (matches the app's existing "illustrative demo data" framing), but gives
// each range a visibly distinct line instead of reusing one static shape.
function seededPoints(seed, count) {
  let x = [...seed].reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const next = () => {
    x = (x * 1103515245 + 12345) & 0x7fffffff;
    return x / 0x7fffffff;
  };
  const points = [];
  let y = 90 + next() * 20;
  for (let i = 0; i < count; i++) {
    y = Math.max(10, Math.min(150, y + (next() - 0.5) * 30));
    points.push([Math.round((600 * i) / (count - 1)), Math.round(y)]);
  }
  return points;
}

const POINTS_BY_RANGE = Object.fromEntries(RANGES.map((r) => [r, seededPoints(r, 24)]));

export default function PriceChart() {
  const [activeRange, setActiveRange] = useState("1Y");

  const { linePoints, areaPath } = useMemo(() => {
    const points = POINTS_BY_RANGE[activeRange];
    return {
      linePoints: points.map(([x, y]) => `${x},${y}`).join(" "),
      areaPath: `M${points.map(([x, y]) => `${x},${y}`).join(" L")} L600,160 L0,160 Z`,
    };
  }, [activeRange]);

  return (
    <div className="price-chart-wrap">
      <svg className="price-chart" viewBox="0 0 600 160" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00c805" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#00c805" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#chartFade)" />
        <polyline
          points={linePoints}
          fill="none"
          stroke="#00c805"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
      <div className="range-pills">
        {RANGES.map((r) => (
          <button
            key={r}
            type="button"
            className={`range-pill${r === activeRange ? " active" : ""}`}
            onClick={() => setActiveRange(r)}
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual: click through all 8 range pills, confirm the line visibly redraws differently for each.

```bash
git add frontend/src/components/PriceChart.jsx
git commit -m "feat: expand chart range set and vary chart data per range"
```

### Task 1.4: Top nav chrome + terminology/consistency pass

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/pages/SchdFundPage.jsx` (hero stat labels)
- Modify: `frontend/src/components/SectorWeights.jsx` (heading casing)
- Modify: `frontend/src/data/schdFund.js` (keep the `schdFundContentText` template in sync with any label wording — it's the raw text handed to `decode_fund_content`, but `decode.py` just reads free text with no schema dependency on these labels, so wording changes here are safe)
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add a search input + account affordance to the app bar** in `App.jsx`

```jsx
<div className="app-bar">
  <div className="app-bar-brand">
    <span className="app-bar-mark">M</span>
    manim-lab
  </div>
  <div className="app-bar-search">
    <input type="text" placeholder="Search" disabled />
  </div>
  <nav className="app-bar-nav">
    <span>Discover</span>
    <span>Portfolio</span>
    <span>Research</span>
  </nav>
  <div className="app-bar-account" aria-hidden="true">
    <span className="app-bar-account-icon">＠</span>
  </div>
</div>
```

- [ ] **Step 2: Terminology fixes** — in `SchdFundPage.jsx` hero stats, rename labels only (keep the same data fields):
  - `"Distribution yield"` → `"Dividend yield (TTM)"`
  - `"AUM"` → `"Net assets"`

  In `SectorWeights.jsx:4`, change `<h2>Sector Weights</h2>` to `<h2>Sector weights</h2>` to match the sentence-case convention used by every other section heading (`Fund details`, `Top holdings`, `Recent distributions`).

  In `schdFund.js`'s `schdFundContentText` template, update the corresponding lines (`Distribution Yield:` → `Dividend Yield (TTM):`, `Assets Under Management:` stays as-is since it's already the realistic full term) so the raw text handed to the backend matches what's shown on screen.

- [ ] **Step 3: Add CSS for the new app-bar elements**

```css
.app-bar-search input {
  background: var(--panel-bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-muted);
  padding: 8px 16px;
  font-size: 13px;
  width: 180px;
}

.app-bar-account-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--panel-bg-2);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--text-muted);
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual: confirm the app bar shows the search box and account icon, and all section headings read in consistent sentence case.

```bash
git add frontend/src/App.jsx frontend/src/pages/SchdFundPage.jsx frontend/src/components/SectorWeights.jsx frontend/src/data/schdFund.js frontend/src/index.css
git commit -m "feat: add app-bar chrome and fix terminology/heading consistency"
```

### ✅ Phase 1 checkpoint

Run the app end to end (`python server.py` + `cd frontend && npm run dev`) and confirm the **existing** floating-button → popup video flow (untouched so far) still works exactly as before. This proves Phase 1 had zero effect on anything server-side, since no file under `webapp/`, `pipeline/`, or `server.py` was touched.

---

## Phase 2 — Backend contract: suggestions become on-demand

Today, `webapp/jobs.py:attach_decode_result` (lines 84-99) creates 4 `VideoJob`s immediately (base + all 3 suggestions), and `webapp/orchestrator.py:_run_session` (lines 40-57) submits all 4 to the render pool, with a 2s head start for the base video. This phase changes it so only the base video auto-generates; suggestions become triggerable on demand via a new endpoint, reusing the existing follow-up submission path rather than adding a parallel one.

### Task 2.1: `webapp/jobs.py` — defer suggestion job creation

**Files:**
- Modify: `webapp/jobs.py`
- Test: `tests/test_webapp.py`

**Interfaces:**
- Produces: `Session.suggestions: list[dict]` (each `{id, question, topic_prompt}`, straight from `decode_fund_content`'s output)
- Produces: `trigger_suggestion(session_id: str, suggestion_id: str) -> tuple[VideoJob | None, bool]` — returns `(None, False)` if the session or suggestion id doesn't exist; returns `(existing_video, False)` if already triggered (idempotent re-click); returns `(new_video, True)` on first trigger.
- Modifies: `session_status_dict()`'s return shape — `videos` now only contains slots that have actually been triggered (starts with just `"base"`); adds a `suggestions` list.

- [ ] **Step 1: Add the `suggestions` field to `Session`**

```python
@dataclass
class Session:
    session_id: str
    decode_status: str = "pending"  # pending|running|done|error
    decode_error: str | None = None
    fund_name: str | None = None
    base_topic_prompt: str | None = None
    suggestions: list[dict] = field(default_factory=list)  # [{id, question, topic_prompt}]
    video_slots: dict[str, str] = field(default_factory=dict)  # "base" -> video_id, "suggestion_<id>" -> video_id
```

- [ ] **Step 2: Rewrite `attach_decode_result`** to create only the base job

```python
def attach_decode_result(session_id: str, decode: dict) -> None:
    """Creates the base VideoJob and stores the 3 suggestion prompts. Suggestion
    videos are created on demand via trigger_suggestion(), not here."""
    base_video = create_video("base", decode["base_topic_prompt"])

    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return
        session.fund_name = decode["fund_name"]
        session.base_topic_prompt = decode["base_topic_prompt"]
        session.suggestions = decode["suggestions"]
        session.video_slots = {"base": base_video.video_id}
        session.decode_status = "done"
```

- [ ] **Step 3: Add `trigger_suggestion`**

```python
def trigger_suggestion(session_id: str, suggestion_id: str) -> tuple[VideoJob | None, bool]:
    """Returns (video, created). created=False means it was already triggered
    (idempotent re-click) or suggestion_id/session_id doesn't exist (video is None)."""
    slot = f"suggestion_{suggestion_id}"
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return None, False
        existing_video_id = session.video_slots.get(slot)
        if existing_video_id is not None:
            return _videos.get(existing_video_id), False
        suggestion = next((s for s in session.suggestions if s["id"] == suggestion_id), None)
        if suggestion is None:
            return None, False

    video = create_video("suggestion", suggestion["topic_prompt"], label=suggestion["question"])
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return None, False
        session.video_slots[slot] = video.video_id
    return video, True
```

- [ ] **Step 4: Update `session_status_dict`** to expose `suggestions`

```python
def session_status_dict(session_id: str) -> dict | None:
    session = get_session(session_id)
    if session is None:
        return None
    return {
        "session_id": session.session_id,
        "decode_status": session.decode_status,
        "decode_error": session.decode_error,
        "fund_name": session.fund_name,
        "base_topic_prompt": session.base_topic_prompt,
        "videos": {slot: video_status_dict(vid) for slot, vid in session.video_slots.items()},
        "suggestions": [
            {
                "id": s["id"],
                "question": s["question"],
                "video_id": session.video_slots.get(f"suggestion_{s['id']}"),
            }
            for s in session.suggestions
        ],
    }
```

- [ ] **Step 5: Update the existing test that assumed eager suggestion creation**

In `tests/test_webapp.py`, `test_get_session_status_full_shape` (lines 51-71) currently asserts `set(data["videos"].keys()) == {"base", "suggestion_1", "suggestion_2", "suggestion_3"}` and `data["videos"]["suggestion_1"]["label"] == "What if A?"`. Replace those two assertions:

```python
    resp = client.get(f"/api/sessions/{session_id}")
    data = resp.get_json()
    assert data["decode_status"] == "done"
    assert data["fund_name"] == "Mock Fund"
    assert set(data["videos"].keys()) == {"base"}
    assert data["videos"]["base"]["status"] == "queued"
    assert data["videos"]["base"]["video_url"] is None
    assert [s["id"] for s in data["suggestions"]] == ["a", "b", "c"]
    assert data["suggestions"][0] == {"id": "a", "question": "What if A?", "video_id": None}
```

- [ ] **Step 6: Add new tests for `trigger_suggestion`**

```python
def test_trigger_suggestion_creates_video_on_first_call():
    session = jobs.create_session()
    jobs.attach_decode_result(session.session_id, _decode_result())

    video, created = jobs.trigger_suggestion(session.session_id, "a")

    assert created is True
    assert video.kind == "suggestion"
    assert video.label == "What if A?"
    assert video.topic_prompt == "Explain A."


def test_trigger_suggestion_is_idempotent():
    session = jobs.create_session()
    jobs.attach_decode_result(session.session_id, _decode_result())

    first, first_created = jobs.trigger_suggestion(session.session_id, "a")
    second, second_created = jobs.trigger_suggestion(session.session_id, "a")

    assert first_created is True
    assert second_created is False
    assert first.video_id == second.video_id


def test_trigger_suggestion_unknown_id_returns_none():
    session = jobs.create_session()
    jobs.attach_decode_result(session.session_id, _decode_result())

    video, created = jobs.trigger_suggestion(session.session_id, "does_not_exist")

    assert video is None
    assert created is False
```

(`_decode_result()` already exists at the top of `tests/test_webapp.py:7-16` — reuse it, do not duplicate it. If these new tests live better in a `tests/test_jobs.py` file instead, create that file and import `from webapp import jobs` — check whether one already exists first with `ls tests/test_jobs.py`.)

- [ ] **Step 7: Run tests and commit**

Run: `python -m pytest tests/test_webapp.py tests/test_jobs.py -v` (adjust path if step 6's tests went into `test_webapp.py` instead)
Expected: all pass.

```bash
git add webapp/jobs.py tests/test_webapp.py
git commit -m "feat: defer suggestion video creation until explicitly triggered"
```

### Task 2.2: `webapp/orchestrator.py` — stop auto-submitting suggestions

**Files:**
- Modify: `webapp/orchestrator.py`

- [ ] **Step 1: Simplify `_run_session`** — remove the suggestion loop and the priority-delay sleep (no longer needed once only one video auto-starts)

```python
def _run_session(session_id: str, fund_content: str) -> None:
    jobs.update_session(session_id, decode_status="running")
    try:
        decode = decode_fund_content(fund_content)
    except DecodeError as e:
        jobs.update_session(session_id, decode_status="error", decode_error=str(e))
        return

    jobs.attach_decode_result(session_id, decode)
    session = jobs.get_session(session_id)

    base_id = session.video_slots["base"]
    _pipeline_pool.submit(_run_video_pipeline, base_id, decode["base_topic_prompt"])
```

- [ ] **Step 2: Remove the now-unused `BASE_PRIORITY_DELAY_SEC` constant and `import time`** (both only existed to support the removed sleep — confirm nothing else in the file uses `time` before deleting the import).

- [ ] **Step 3: Run existing orchestrator tests and commit**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: all pass unchanged (this test only exercises `_run_video_pipeline`, not `_run_session`, so it's unaffected).

```bash
git add webapp/orchestrator.py
git commit -m "refactor: stop auto-generating suggestion videos on session start"
```

### Task 2.3: `webapp/app.py` — new suggestion-trigger endpoint

**Files:**
- Modify: `webapp/app.py`
- Test: `tests/test_webapp.py`

**Interfaces:**
- Consumes: `jobs.trigger_suggestion(session_id, suggestion_id) -> tuple[VideoJob | None, bool]` (Task 2.1), `orchestrator.start_followup(video_id, topic_prompt) -> None` (existing, unchanged — its body is generic enough to reuse here as-is).
- Produces: `POST /api/sessions/<session_id>/suggestions/<suggestion_id>/generate` → `202 {"video_id": ..., "status": "queued"}`, or `404`/`409` errors.

- [ ] **Step 1: Add the route** in `webapp/app.py`, after the existing `followup` route

```python
    @app.post("/api/sessions/<session_id>/suggestions/<suggestion_id>/generate")
    def generate_suggestion(session_id, suggestion_id):
        session = jobs.get_session(session_id)
        if session is None:
            return jsonify({"error": "session not found"}), 404
        if session.decode_status != "done":
            return jsonify({"error": "session not ready"}), 409

        video, created = jobs.trigger_suggestion(session_id, suggestion_id)
        if video is None:
            return jsonify({"error": "unknown suggestion id"}), 404
        if created:
            orchestrator.start_followup(video.video_id, video.topic_prompt)
        return jsonify({"video_id": video.video_id, "status": "queued"}), 202
```

- [ ] **Step 2: Add tests** in `tests/test_webapp.py`

```python
def test_generate_suggestion_success(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/suggestions/a/generate")
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["video_id"].startswith("vid_")

    video = jobs.get_video(data["video_id"])
    assert video.kind == "suggestion"
    assert video.label == "What if A?"


def test_generate_suggestion_idempotent_returns_same_video_id(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    first = client.post(f"/api/sessions/{session_id}/suggestions/a/generate").get_json()
    second = client.post(f"/api/sessions/{session_id}/suggestions/a/generate").get_json()

    assert first["video_id"] == second["video_id"]


def test_generate_suggestion_404_unknown_suggestion_id(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/suggestions/does_not_exist/generate")
    assert resp.status_code == 404


def test_generate_suggestion_404_unknown_session(client):
    resp = client.post("/api/sessions/sess_nope/suggestions/a/generate")
    assert resp.status_code == 404


def test_generate_suggestion_409_when_session_not_ready(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]

    resp = client.post(f"/api/sessions/{session_id}/suggestions/a/generate")
    assert resp.status_code == 409
```

- [ ] **Step 3: Run full backend test suite and commit**

Run: `python -m pytest -v`
Expected: all pass, including the untouched CLI/pipeline tests (`test_planner.py`, `test_codegen.py`, `test_renderer.py`, `test_stitch.py`, `test_make_video.py`, `test_decode.py`, `test_config.py`, `test_llm.py`) — confirming this phase's changes are fully contained to the webapp layer.

```bash
git add webapp/app.py tests/test_webapp.py
git commit -m "feat: add on-demand suggestion video generation endpoint"
```

### ✅ Phase 2 checkpoint

Verify entirely via `pytest` and curl — **do not** click through the still-old frontend yet. It will show suggestions as permanently spinning (since they're no longer eagerly created) until Phase 3 replaces it; that's an expected, temporary intermediate state, not a regression.

```bash
python -m pytest -v
python server.py &  # separate terminal in practice
curl -s -X POST http://localhost:5000/api/sessions -H "Content-Type: application/json" -d '{"fund_content":"SCHD test"}'
# then, using the returned session_id:
curl -s http://localhost:5000/api/sessions/<session_id>
curl -s -X POST http://localhost:5000/api/sessions/<session_id>/suggestions/<a_suggestion_id>/generate
```

---

## Phase 3 — Inline video-experience frontend

Replaces `FloatingWidgetButton.jsx` + `VideoPanel.jsx` with an always-visible module embedded in `SchdFundPage.jsx`, built against Phase 2's contract. Reuses `useSessionStatus`, `useVideoStatus`, `VideoPlayer`, and `FollowupInput` as-is — none of those need to change.

### Task 3.1: `api.js` — add the suggestion-trigger call

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Add `generateSuggestion`**

```js
export function generateSuggestion(sessionId, suggestionId) {
  return request(`/api/sessions/${sessionId}/suggestions/${suggestionId}/generate`, {
    method: "POST",
  });
}
```

- [ ] **Step 2: Verify and commit**

Run: `cd frontend && npm run lint`

```bash
git add frontend/src/api.js
git commit -m "feat: add generateSuggestion API call"
```

### Task 3.2: `QuestionChip.jsx` — unify suggestion/follow-up chip rendering

This replaces both `SuggestionButton.jsx` and the inline `FollowupEntry` function currently defined inside `VideoPanel.jsx` (lines 11-34) with one component that handles three states: **not yet triggered** (plain clickable prompt, no `video_id` yet), **generating** (polling, spinner), **ready** (clickable to view).

**Files:**
- Create: `frontend/src/components/QuestionChip.jsx`
- Delete: `frontend/src/components/SuggestionButton.jsx`

**Interfaces:**
- Consumes: `useVideoStatus(videoId)` (existing hook, unchanged — already handles `videoId === null` by never polling and leaving `status` as `null`, per `frontend/src/hooks/useVideoStatus.js:11-13`).
- Produces: `<QuestionChip label={string} videoId={string|null} active={bool} onSelect={(videoId) => void} onTrigger={() => void} />`

- [ ] **Step 1: Write the component**

```jsx
import { useVideoStatus } from "../hooks/useVideoStatus";

export default function QuestionChip({ label, videoId, active, onSelect, onTrigger }) {
  const { status } = useVideoStatus(videoId);
  const started = Boolean(videoId);
  const ready = status?.status === "done";
  const failed = status?.status === "error";

  function handleClick() {
    if (!started) {
      onTrigger();
      return;
    }
    if (ready) onSelect(videoId);
  }

  let text = label;
  if (failed) text = `${label} (failed)`;
  else if (started && !ready) text = `${label} — ${status?.stage_detail || status?.status || "generating…"}`;

  return (
    <button
      type="button"
      className={`question-chip${active ? " active" : ""}${failed ? " failed" : ""}`}
      disabled={started && !ready && !failed}
      onClick={handleClick}
    >
      {started && !ready && !failed && <span className="spinner" aria-hidden="true" />}
      <span className="question-chip-label">{text}</span>
    </button>
  );
}
```

- [ ] **Step 2: Delete `SuggestionButton.jsx`** (`rm frontend/src/components/SuggestionButton.jsx`) — its only consumer, `VideoPanel.jsx`, is removed in Task 3.3.

- [ ] **Step 3: Verify and commit**

Run: `cd frontend && npm run lint` (will show unused-import errors in `VideoPanel.jsx`/`FloatingWidgetButton.jsx` until Task 3.3 removes them — that's expected mid-phase; the phase-level checkpoint below is what must be clean.)

```bash
git add frontend/src/components/QuestionChip.jsx
git rm frontend/src/components/SuggestionButton.jsx
git commit -m "feat: add unified QuestionChip component"
```

### Task 3.3: `ExplainModule.jsx` — the inline video experience

Replaces `VideoPanel.jsx`'s role. Mounted directly inside `SchdFundPage.jsx` (not as a popup overlay). Session creation now happens automatically on mount instead of on a button click, since "click a floating button to start" no longer exists.

**Files:**
- Create: `frontend/src/components/ExplainModule.jsx`
- Delete: `frontend/src/components/FloatingWidgetButton.jsx`
- Delete: `frontend/src/components/VideoPanel.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/pages/SchdFundPage.jsx`

**Interfaces:**
- Consumes: `createSession`, `postFollowup`, `generateSuggestion`, `videoFileUrl` (`api.js`), `useSessionStatus` (existing hook, unchanged), `QuestionChip` (Task 3.2), `VideoPlayer`/`FollowupInput` (existing, unchanged).
- Produces: `<ExplainModule fundContentText={string} contextualQuestion={string|null} onContextualHandled={() => void} />` — the `contextualQuestion` prop is how Task 3.4's per-data-point triggers feed a question into this module (lifted state, since they're siblings under `SchdFundPage`).

- [ ] **Step 1: Write `ExplainModule.jsx`**

```jsx
import { useEffect, useState } from "react";
import { createSession, generateSuggestion, postFollowup, videoFileUrl } from "../api";
import { useSessionStatus } from "../hooks/useSessionStatus";
import FollowupInput from "./FollowupInput";
import QuestionChip from "./QuestionChip";
import VideoPlayer from "./VideoPlayer";

export default function ExplainModule({ fundContentText, contextualQuestion, onContextualHandled }) {
  const [sessionId, setSessionId] = useState(null);
  const [initError, setInitError] = useState(null);
  const { status, error } = useSessionStatus(sessionId);
  const [activeVideoId, setActiveVideoId] = useState(null);
  const [suggestionVideoIds, setSuggestionVideoIds] = useState({});
  const [extraQuestions, setExtraQuestions] = useState([]);
  const [askError, setAskError] = useState(null);

  useEffect(() => {
    createSession(fundContentText)
      .then((result) => setSessionId(result.session_id))
      .catch((err) => setInitError(err.message));
  }, [fundContentText]);

  const baseVideo = status?.videos?.base;
  const currentVideoId = activeVideoId || baseVideo?.video_id;
  const currentVideoReady = currentVideoId && currentVideoId === baseVideo?.video_id
    ? baseVideo.status === "done"
    : true; // non-base chips only become selectable once QuestionChip confirms "done"
  const currentVideoUrl = currentVideoId && currentVideoReady ? videoFileUrl(currentVideoId) : null;

  async function handleAsk(question) {
    setAskError(null);
    try {
      const result = await postFollowup(sessionId, question);
      setExtraQuestions((qs) => [...qs, { videoId: result.video_id, label: question }]);
    } catch (err) {
      setAskError(err.message);
    }
  }

  useEffect(() => {
    if (!contextualQuestion || !sessionId) return;
    handleAsk(contextualQuestion).finally(onContextualHandled);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextualQuestion, sessionId]);

  async function handleTriggerSuggestion(suggestionId) {
    setSuggestionVideoIds((m) => (m[suggestionId] ? m : { ...m, [suggestionId]: "pending" }));
    try {
      const result = await generateSuggestion(sessionId, suggestionId);
      setSuggestionVideoIds((m) => ({ ...m, [suggestionId]: result.video_id }));
    } catch (err) {
      setAskError(err.message);
      setSuggestionVideoIds((m) => {
        const next = { ...m };
        delete next[suggestionId];
        return next;
      });
    }
  }

  return (
    <section className="explain-module">
      <div className="explain-module-header">
        <span className="explain-module-title">✨ Don't understand something?</span>
        <span className="explain-module-subtitle">Ask AI to explain any part of this fund, visually.</span>
      </div>

      {initError && <p className="panel-error">{initError}</p>}
      {error && <p className="panel-error">{error}</p>}

      {(status?.decode_status === "pending" || status?.decode_status === "running") && (
        <p className="panel-status">Reading the fund page…</p>
      )}
      {status?.decode_status === "error" && (
        <p className="panel-error">Couldn't read the fund page: {status.decode_error}</p>
      )}
      {baseVideo && baseVideo.status !== "done" && baseVideo.status !== "error" && !activeVideoId && (
        <p className="panel-status">
          Generating your explanation — {baseVideo.stage_detail || baseVideo.status}…
        </p>
      )}
      {baseVideo?.status === "error" && !activeVideoId && (
        <p className="panel-error">Video generation failed: {baseVideo.error}</p>
      )}

      {currentVideoUrl && (
        <VideoPlayer
          src={currentVideoUrl}
          title={currentVideoId === baseVideo?.video_id ? status.fund_name : undefined}
        />
      )}

      {status?.decode_status === "done" && (
        <div className="chip-row">
          <QuestionChip
            label={baseVideo?.title || "Overview"}
            videoId={baseVideo?.video_id}
            active={currentVideoId === baseVideo?.video_id}
            onSelect={setActiveVideoId}
            onTrigger={() => {}}
          />
          {status.suggestions.map((s) => {
            const videoId = suggestionVideoIds[s.id] === "pending" ? null : suggestionVideoIds[s.id] || s.video_id;
            return (
              <QuestionChip
                key={s.id}
                label={s.question}
                videoId={videoId}
                active={currentVideoId === videoId}
                onSelect={setActiveVideoId}
                onTrigger={() => handleTriggerSuggestion(s.id)}
              />
            );
          })}
          {extraQuestions.map((q) => (
            <QuestionChip
              key={q.videoId}
              label={q.label}
              videoId={q.videoId}
              active={currentVideoId === q.videoId}
              onSelect={setActiveVideoId}
              onTrigger={() => {}}
            />
          ))}
        </div>
      )}

      {status?.decode_status === "done" && (
        <>
          <FollowupInput onSubmit={handleAsk} disabled={false} />
          {askError && <p className="panel-error">{askError}</p>}
        </>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Mount it in `SchdFundPage.jsx`**, right after the hero stats / before `<FundDetailsTable />`, replacing the removed floating widget:

```jsx
import { useState } from "react";
import ExplainModule from "../components/ExplainModule";
// ...other existing imports
import { schdFund, schdFundContentText } from "../data/schdFund";

export default function SchdFundPage() {
  const [contextualQuestion, setContextualQuestion] = useState(null);
  // ...existing toastMessage state from Task 1.1

  return (
    <div className="fund-page">
      <header className="fund-header">
        {/* ...existing header content unchanged... */}
      </header>

      <ExplainModule
        fundContentText={schdFundContentText}
        contextualQuestion={contextualQuestion}
        onContextualHandled={() => setContextualQuestion(null)}
      />

      <FundDetailsTable fund={schdFund} onExplain={setContextualQuestion} />
      <TopHoldingsTable holdings={schdFund.topHoldings} onExplain={setContextualQuestion} />
      <DistributionHistory history={schdFund.distributionHistory} onExplain={setContextualQuestion} />
      <SectorWeights sectors={schdFund.sectorWeights} />

      <TradeBar onAction={handleTradeAction} />
      <footer className="fund-footer">Illustrative demo data, not live market data.</footer>
      <Toast message={toastMessage} onDone={() => setToastMessage(null)} />
    </div>
  );
}
```

(`onExplain` props on the table components are wired up in Task 3.4 — this step just plumbs the callback through.)

- [ ] **Step 3: Add CSS for the module** (`ExplainModule`/`QuestionChip` reference these class names as of Task 3.2/this step — added here, not deferred, so nothing renders unstyled)

```css
.explain-module {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px 22px;
  margin-bottom: 16px;
}

.explain-module-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 12px;
}

.explain-module-title {
  font-weight: 700;
  font-size: 15px;
}

.explain-module-subtitle {
  font-size: 13px;
  color: var(--text-muted);
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0;
}

.question-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--border-strong);
  background: var(--panel-bg-2);
  color: var(--text);
  border-radius: 999px;
  padding: 9px 16px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.question-chip:hover:not(:disabled) {
  border-color: var(--text-faint);
}

.question-chip:disabled {
  cursor: default;
  opacity: 0.55;
}

.question-chip.active {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--accent-contrast);
  font-weight: 700;
}

.question-chip.failed {
  border-color: var(--danger);
  color: var(--danger);
  background: var(--danger-bg);
}
```

(`.spinner`, `.panel-status`, `.panel-error`, `.video-player-wrap`, `.video-title`, `.video-player`, `.followup-form`, `.followup-input`, `.followup-submit` already exist in `index.css` from the old popup and are reused as-is by `ExplainModule`/`VideoPlayer`/`FollowupInput` unchanged — only the popup-container-specific rules (`.video-panel-overlay`, `.video-panel`, `.video-panel-close`) and the old chip names (`.suggestion-row`, `.suggestion-button`, `.suggestion-label`) become dead code, cleaned up in Task 3.5 once `VideoPanel.jsx`/`SuggestionButton.jsx` are deleted below.)

- [ ] **Step 4: Remove the floating widget from `App.jsx`**

```jsx
import SchdFundPage from "./pages/SchdFundPage";

export default function App() {
  return (
    <>
      <div className="app-bar">{/* ...unchanged from Phase 1... */}</div>
      <SchdFundPage />
    </>
  );
}
```

- [ ] **Step 5: Delete the superseded files**

```bash
git rm frontend/src/components/FloatingWidgetButton.jsx frontend/src/components/VideoPanel.jsx
```

- [ ] **Step 6: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual (needs `python server.py` running too): load the page, confirm the module appears inline and immediately starts generating the base video with live progress text, confirm suggestion chips show as plain (non-spinning) prompts until clicked, confirm clicking one starts it generating and it becomes selectable once done, confirm free-text follow-up still works.

```bash
git add frontend/src/components/ExplainModule.jsx frontend/src/pages/SchdFundPage.jsx frontend/src/App.jsx
git commit -m "feat: replace floating popup with inline ExplainModule"
```

### Task 3.4: Contextual "explain this" triggers on data points

**Files:**
- Modify: `frontend/src/components/FundDetailsTable.jsx`
- Modify: `frontend/src/components/TopHoldingsTable.jsx`
- Modify: `frontend/src/components/DistributionHistory.jsx`

**Interfaces:**
- Consumes: `onExplain: (question: string) => void` prop (passed from `SchdFundPage.jsx`'s `setContextualQuestion`, wired in Task 3.3 step 2).

- [ ] **Step 1: `FundDetailsTable.jsx`** — add a trigger next to each stat cell

```jsx
export default function FundDetailsTable({ fund, onExplain }) {
  const cells = [
    ["Category", fund.category],
    ["Provider", fund.provider],
    ["Inception date", fund.inceptionDate],
    ["Distribution frequency", fund.distributionFrequency],
    ["Benchmark", fund.benchmark],
    ["Number of holdings", fund.numberOfHoldings],
  ];

  return (
    <section className="fund-section">
      <h2>Fund details</h2>
      <div className="stat-grid">
        {cells.map(([label, value]) => (
          <div className="stat-cell" key={label}>
            <div className="stat-cell-label-row">
              <span className="stat-label">{label}</span>
              <button
                type="button"
                className="explain-trigger"
                aria-label={`Explain ${label}`}
                onClick={() => onExplain(`Explain what "${label}" (${value}) means for this fund.`)}
              >
                ✨
              </button>
            </div>
            <span className="stat-value">{value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: `TopHoldingsTable.jsx`** — add a trigger per holding row

```jsx
export default function TopHoldingsTable({ holdings, onExplain }) {
  const maxWeight = Math.max(...holdings.map((h) => h.weightPct));

  return (
    <section className="fund-section">
      <h2>Top holdings</h2>
      <div className="holdings-list">
        {holdings.map((h) => (
          <div className="holding-row" key={h.ticker}>
            <div className="holding-id">
              <span className="holding-ticker">{h.ticker}</span>
              <span className="holding-name">{h.name}</span>
            </div>
            <div className="holding-bar-track">
              <div className="holding-bar-fill" style={{ width: `${(h.weightPct / maxWeight) * 100}%` }} />
            </div>
            <span className="holding-weight">{h.weightPct}%</span>
            <button
              type="button"
              className="explain-trigger"
              aria-label={`Explain ${h.name}`}
              onClick={() => onExplain(`Explain why ${h.name} (${h.ticker}) is ${h.weightPct}% of this fund.`)}
            >
              ✨
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
```

(Adjust `.holding-row`'s CSS grid in `index.css` — `grid-template-columns: 120px 1fr 44px;` — to add a fifth column for the trigger, e.g. `120px 1fr 44px 28px`.)

- [ ] **Step 3: `DistributionHistory.jsx`** — add a trigger per distribution row

```jsx
export default function DistributionHistory({ history, onExplain }) {
  return (
    <section className="fund-section">
      <h2>Recent distributions</h2>
      <div className="distribution-list">
        {history.map((d) => (
          <div className="distribution-row" key={d.exDate}>
            <span className="distribution-date">{d.exDate}</span>
            <span className="distribution-amount">+${d.amount.toFixed(2)}</span>
            <button
              type="button"
              className="explain-trigger"
              aria-label={`Explain the ${d.exDate} distribution`}
              onClick={() => onExplain(`Explain the $${d.amount.toFixed(2)} distribution paid on ${d.exDate}.`)}
            >
              ✨
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add shared CSS**

```css
.stat-cell-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.explain-trigger {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
  opacity: 0.6;
  transition: opacity 0.15s ease;
}

.explain-trigger:hover {
  opacity: 1;
}
```

- [ ] **Step 5: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual: click a "✨" next to a stat/holding/distribution row, confirm the page scrolls attention to (or the user notices) the `ExplainModule` starting a new chip for that question, and that it generates and plays correctly.

```bash
git add frontend/src/components/FundDetailsTable.jsx frontend/src/components/TopHoldingsTable.jsx frontend/src/components/DistributionHistory.jsx frontend/src/index.css
git commit -m "feat: add contextual explain triggers to fund detail rows"
```

### Task 3.5: Remove dead CSS from the old popup

`.explain-module`/`.chip-row`/`.question-chip*` were already added fresh in Task 3.3 (Step 3), so nothing needs renaming here — this task only deletes the rules that became truly unused once `VideoPanel.jsx`/`FloatingWidgetButton.jsx`/`SuggestionButton.jsx` were deleted (Tasks 3.2/3.3).

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Remove now-dead rules**: `.floating-widget-button`, `.floating-widget-icon`, `.floating-widget-error`, `.video-panel-overlay`, `.video-panel`, `.video-panel-close`, `.suggestion-row`, `.suggestion-button`, `.suggestion-label` (all superseded by `ExplainModule`/`Toast`/`QuestionChip`'s `.chip-row`/`.question-chip*` rules).

- [ ] **Step 2: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual: full visual pass of the module — confirm no dead/unused class names remain (`grep -rn "floating-widget\|video-panel\|suggestion-button\|suggestion-row" frontend/src/` should return nothing).

```bash
git add frontend/src/index.css
git commit -m "refactor: remove dead CSS from the removed popup components"
```

### ✅ Phase 3 checkpoint

Full manual run-through with both servers up:
1. Load the page — base video starts generating automatically inline, with live stage text.
2. Click a suggestion chip — it starts generating, becomes playable when done.
3. Click a "✨" contextual trigger on a holding/stat/distribution row — a new chip appears and plays once ready.
4. Type a free-text follow-up — same behavior as before.
5. `cd frontend && npm run lint && npm run build` clean; `python -m pytest` clean.

---

## Phase 4 — Cohesion pass

**Files:** likely small touch-ups across `frontend/src/index.css` and whichever components look inconsistent once Phases 1 and 3 are both in place (e.g. spacing between `TradeBar` and `ExplainModule`, making sure `explain-trigger` buttons don't visually clash with the new app-bar/watchlist elements).

- [ ] **Step 1:** Full click-through of the whole page with both phases' changes live — chart ranges, watchlist star, trade bar + toast, inline explain module, contextual triggers, follow-up input.
- [ ] **Step 2:** Fix any visual inconsistencies found (spacing, color, type scale) directly in `index.css`, reusing existing `--*` tokens rather than introducing new ad hoc values.
- [ ] **Step 3:** Final verification and commit.

Run: `python -m pytest -v && cd frontend && npm run lint && npm run build`

```bash
git add -A
git commit -m "polish: cohesion pass across Robinhood realism and inline explain module"
```

---

## Verification summary

- **Phase 1:** `npm run lint && npm run build` after each task + manual browser check; old video popup flow must still work unchanged at the end (proves zero backend impact).
- **Phase 2:** `python -m pytest -v` after each task; curl checks against a running `python server.py` before any frontend work begins.
- **Phase 3:** `npm run lint && npm run build` after each task + full manual run-through at the end (base video, suggestion click, contextual trigger, free-text follow-up).
- **Phase 4:** both suites green, full manual click-through.
