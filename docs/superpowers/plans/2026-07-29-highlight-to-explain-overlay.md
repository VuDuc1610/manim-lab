# Highlight-to-Explain Overlay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline `ExplainModule` box with a full-screen, blurred-backdrop overlay experience: select any text on the fund page (or click a small persistent entry button) → the page blurs behind a centered card showing live generation progress → once the video is ready, a deliberate "▶ Watch" click expands it to a large in-overlay player. Closing returns to the normal page. This replaces *all* video generation/watching on the page (base video, the 3 suggestions, follow-ups) — there is no more inline box.

**Architecture:** Pure frontend rework, zero backend changes. The existing session/video API contract (`createSession`, `getSessionStatus`, `generateSuggestion`, `postFollowup`, `getVideoStatus`, `videoFileUrl` in `frontend/src/api.js`) already supports everything this needs — the overlay just presents the same underlying state differently. "Different pages" is simulated via a full-viewport overlay (no `react-router`, no URL changes), not real routing. The existing per-row "✨" icon-button triggers become redundant once any text anywhere is selectable-and-explainable, so they're removed.

**Tech Stack:** Vite + React frontend, no test framework (`npm run lint` + `npm run build` + reasoning-through-the-code are the verification tools, same as prior work in this repo). No headless browser tool is available in this environment — verification is lint/build plus careful manual tracing of the state machine, with real browser confirmation left to the human partner via the running dev server.

## Global Constraints

- No backend changes. Do not touch `webapp/` or `pipeline/` — this plan is 100% `frontend/src/`.
- No new dependencies (no `react-router-dom`, no selection/positioning libraries) — the native Selection API and `getBoundingClientRect()` are sufficient.
- Reuse existing pieces as-is: `api.js`, `useSessionStatus.js`, `useVideoStatus.js`, `VideoPlayer.jsx`, `FollowupInput.jsx`. Only `QuestionChip.jsx` gets a small, deliberate behavior change (below).
- New CSS reuses existing `--*` custom properties from `frontend/src/index.css` — no new ad hoc colors/shadows.
- `frontend/src/main.jsx` wraps the app in `<StrictMode>`, which double-invokes mount effects in dev — any new `useEffect` that fires a real API call on mount needs the same `useRef` guard pattern already used in the current `ExplainModule.jsx` (`sessionInitRef`).
- A backend follow-up's phrasing (`webapp/app.py`'s `/followup` route: `"{base_topic_prompt} Specifically, explain what would change if: {question}"`) is tuned for what-if questions, not literal "explain this term" requests. Since text selections can be short fragments like `"0.06%"`, wrap raw selections into an explanatory phrasing client-side before sending (`Explain what "{text}" means in the context of {fund name}.`) rather than sending the raw fragment — keeps this a frontend-only change.

---

### Task 1: `useTextSelection` hook

**Files:**
- Create: `frontend/src/hooks/useTextSelection.js`

**Interfaces:**
- Produces: `useTextSelection() -> { selection: { text: string, rect: DOMRect } | null, clear: () => void }` — `selection` is `null` whenever nothing (or only whitespace) is selected.

- [ ] **Step 1: Write the hook**

```js
import { useEffect, useState } from "react";

export function useTextSelection() {
  const [selection, setSelection] = useState(null);

  useEffect(() => {
    function handleSelectionChange() {
      const sel = window.getSelection();
      const text = sel ? sel.toString().trim() : "";
      if (!text || sel.rangeCount === 0) {
        setSelection(null);
        return;
      }
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      setSelection({ text, rect });
    }

    document.addEventListener("selectionchange", handleSelectionChange);
    return () => document.removeEventListener("selectionchange", handleSelectionChange);
  }, []);

  function clear() {
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  }

  return { selection, clear };
}
```

- [ ] **Step 2: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`

```bash
git add frontend/src/hooks/useTextSelection.js
git commit -m "feat: add useTextSelection hook for highlight-to-explain"
```

---

### Task 2: `SelectionExplainButton` component

**Files:**
- Create: `frontend/src/components/SelectionExplainButton.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: the `selection` shape from Task 1 (`{ text, rect } | null`).
- Produces: `<SelectionExplainButton selection={...} onExplain={(text) => void} />` — renders nothing when `selection` is `null`; renders a small floating pill positioned just above the selection otherwise, calling `onExplain(selection.text)` on click.

- [ ] **Step 1: Write the component**

```jsx
export default function SelectionExplainButton({ selection, onExplain }) {
  if (!selection) return null;
  const { text, rect } = selection;

  const style = {
    top: Math.max(8, rect.top - 40),
    left: rect.left + rect.width / 2,
  };

  return (
    <button
      type="button"
      className="selection-explain-button"
      style={style}
      onClick={() => onExplain(text)}
    >
      ✨ Explain this
    </button>
  );
}
```

- [ ] **Step 2: Add CSS**

```css
.selection-explain-button {
  position: fixed;
  transform: translateX(-50%);
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: var(--shadow);
  z-index: 70;
  white-space: nowrap;
}
```

- [ ] **Step 3: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`

```bash
git add frontend/src/components/SelectionExplainButton.jsx frontend/src/index.css
git commit -m "feat: add floating SelectionExplainButton"
```

---

### Task 3: `ExplainEntryButton` component

**Files:**
- Create: `frontend/src/components/ExplainEntryButton.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: `<ExplainEntryButton onClick={() => void} />` — a small persistent floating action button (bottom-right), the one non-text-selection way to open the overlay (needed for the base fund video / suggestion chips, which aren't tied to a specific text selection).

- [ ] **Step 1: Write the component**

```jsx
export default function ExplainEntryButton({ onClick }) {
  return (
    <button type="button" className="explain-entry-button" onClick={onClick} aria-label="Explain this fund">
      ✨
    </button>
  );
}
```

- [ ] **Step 2: Add CSS**

```css
.explain-entry-button {
  position: fixed;
  right: 28px;
  bottom: 28px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: var(--accent);
  color: var(--accent-contrast);
  font-size: 20px;
  cursor: pointer;
  box-shadow: var(--shadow-cta);
  z-index: 40;
  transition: transform 0.15s ease;
}

.explain-entry-button:hover {
  transform: translateY(-1px);
}
```

- [ ] **Step 3: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`

```bash
git add frontend/src/components/ExplainEntryButton.jsx frontend/src/index.css
git commit -m "feat: add persistent ExplainEntryButton"
```

---

### Task 4: `QuestionChip` behavior change + `ExplainOverlay` component

This is the core task. `QuestionChip.jsx` (from prior work, unchanged file otherwise) currently disables its button entirely while a video is generating, so there's no way to tap back into an in-progress question's detail view — only "not started" (→ trigger) and "ready" (→ select) are clickable. The new overlay needs *any* chip (generating, ready, or failed) to be tappable so the user can jump into its focused progress/ready/error view. Only the not-started→trigger and the explicit pending-race guard stay as hard blocks.

**Files:**
- Modify: `frontend/src/components/QuestionChip.jsx`
- Create: `frontend/src/components/ExplainOverlay.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `createSession`, `generateSuggestion`, `postFollowup`, `videoFileUrl` (`api.js`), `useSessionStatus`, `useVideoStatus` (existing hooks, unchanged), `QuestionChip` (this task's modified version), `VideoPlayer`, `FollowupInput` (existing, unchanged).
- Produces: `<ExplainOverlay fundContentText={string} open={bool} onClose={() => void} pendingQuestion={{ prompt: string, label: string } | null} onPendingHandled={() => void} />`. `open` controls visibility (component stays mounted and keeps polling even while closed, so background generation isn't interrupted). `pendingQuestion` is how an external trigger (a text selection) asks a specific question and jumps straight to its focused view — mirrors the existing `contextualQuestion`/`onContextualHandled` pattern already used by the current `ExplainModule.jsx`.

- [ ] **Step 1: Modify `QuestionChip.jsx`** — always let a started chip be selected (into its own progress/ready/error view), not just once ready

```jsx
import { useVideoStatus } from "../hooks/useVideoStatus";

export default function QuestionChip({ label, videoId, active, onSelect, onTrigger, disabled: forceDisabled }) {
  const { status } = useVideoStatus(videoId);
  const started = Boolean(videoId);
  const ready = status?.status === "done";
  const failed = status?.status === "error";

  function handleClick() {
    if (forceDisabled) return;
    if (!started) {
      onTrigger();
      return;
    }
    onSelect(videoId);
  }

  let text = label;
  if (failed) text = `${label} (failed)`;
  else if (started && !ready) text = `${label} — ${status?.stage_detail || status?.status || "generating…"}`;
  else if (forceDisabled) text = `${label} — generating…`;

  return (
    <button
      type="button"
      className={`question-chip${active ? " active" : ""}${failed ? " failed" : ""}`}
      disabled={forceDisabled}
      onClick={handleClick}
    >
      {started && !ready && !failed && <span className="spinner" aria-hidden="true" />}
      <span className="question-chip-label">{text}</span>
    </button>
  );
}
```

(Only the `handleClick` body and the `disabled`/`isDisabled` logic changed — `disabled={forceDisabled}` replaces the old `disabled={isDisabled}` computed value, since a chip should now stay clickable while generating or failed.)

- [ ] **Step 2: Write `ExplainOverlay.jsx`**

```jsx
import { useEffect, useRef, useState } from "react";
import { createSession, generateSuggestion, postFollowup, videoFileUrl } from "../api";
import { useSessionStatus } from "../hooks/useSessionStatus";
import { useVideoStatus } from "../hooks/useVideoStatus";
import FollowupInput from "./FollowupInput";
import QuestionChip from "./QuestionChip";
import VideoPlayer from "./VideoPlayer";

export default function ExplainOverlay({ fundContentText, open, onClose, pendingQuestion, onPendingHandled }) {
  const [sessionId, setSessionId] = useState(null);
  const [initError, setInitError] = useState(null);
  const { status, error } = useSessionStatus(sessionId);
  const [suggestionVideoIds, setSuggestionVideoIds] = useState({});
  const [pendingSuggestionIds, setPendingSuggestionIds] = useState(() => new Set());
  const [extraQuestions, setExtraQuestions] = useState([]);
  const [askError, setAskError] = useState(null);
  const [focusedVideoId, setFocusedVideoId] = useState(null);
  const [watching, setWatching] = useState(false);
  const sessionInitRef = useRef(false);

  useEffect(() => {
    // StrictMode double-invokes mount effects in dev; without this guard that
    // means two createSession calls (two full decode + base-video pipeline
    // runs) per page load, which burns Gemini's tight free-tier quota.
    if (sessionInitRef.current) return;
    sessionInitRef.current = true;
    createSession(fundContentText)
      .then((result) => setSessionId(result.session_id))
      .catch((err) => setInitError(err.message));
  }, [fundContentText]);

  useEffect(() => {
    if (!open) {
      setFocusedVideoId(null);
      setWatching(false);
    }
  }, [open]);

  const baseVideo = status?.videos?.base;

  async function handleAsk(question, label = question) {
    setAskError(null);
    try {
      const result = await postFollowup(sessionId, question);
      setExtraQuestions((qs) => [...qs, { videoId: result.video_id, label }]);
      return result;
    } catch (err) {
      setAskError(err.message);
      return null;
    }
  }

  async function handleAskAndFocus(question, label = question) {
    const result = await handleAsk(question, label);
    if (result) setFocusedVideoId(result.video_id);
  }

  useEffect(() => {
    if (!pendingQuestion || !sessionId) return;
    handleAskAndFocus(pendingQuestion.prompt, pendingQuestion.label).finally(onPendingHandled);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion, sessionId]);

  async function handleTriggerSuggestion(suggestionId) {
    // Guard against a second click firing a second real generateSuggestion
    // call (a real Gemini pipeline run) while the first is still in flight —
    // the "pending" video id below is rendered as null to QuestionChip, which
    // alone would leave the chip looking untriggered and clickable again.
    if (pendingSuggestionIds.has(suggestionId)) return;
    setPendingSuggestionIds((s) => new Set(s).add(suggestionId));
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
    } finally {
      setPendingSuggestionIds((s) => {
        const next = new Set(s);
        next.delete(suggestionId);
        return next;
      });
    }
  }

  function labelForVideoId(videoId) {
    if (videoId === baseVideo?.video_id) return baseVideo?.title || "Overview";
    const suggestion = status?.suggestions?.find(
      (s) => (suggestionVideoIds[s.id] === "pending" ? null : suggestionVideoIds[s.id] || s.video_id) === videoId,
    );
    if (suggestion) return suggestion.question;
    const extra = extraQuestions.find((q) => q.videoId === videoId);
    if (extra) return extra.label;
    return "Your question";
  }

  if (!open) return null;

  return (
    <div className="explain-overlay-backdrop" onClick={onClose}>
      <div className={`explain-overlay${watching ? " watching" : ""}`} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="explain-overlay-close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {initError && <p className="panel-error">{initError}</p>}
        {error && <p className="panel-error">{error}</p>}
        {(status?.decode_status === "pending" || status?.decode_status === "running") && (
          <p className="panel-status">Reading the fund page…</p>
        )}
        {status?.decode_status === "error" && (
          <p className="panel-error">Couldn't read the fund page: {status.decode_error}</p>
        )}

        {status?.decode_status === "done" && focusedVideoId && (
          <FocusedView
            videoId={focusedVideoId}
            label={labelForVideoId(focusedVideoId)}
            watching={watching}
            onWatch={() => setWatching(true)}
            onBack={() => (watching ? setWatching(false) : setFocusedVideoId(null))}
          />
        )}

        {status?.decode_status === "done" && !focusedVideoId && (
          <>
            <div className="explain-overlay-header">
              <span className="explain-overlay-title">✨ Don't understand something?</span>
              <span className="explain-overlay-subtitle">Ask AI to explain any part of this fund, visually.</span>
            </div>

            <div className="chip-row">
              <QuestionChip
                label={baseVideo?.title || "Overview"}
                videoId={baseVideo?.video_id}
                active={false}
                onSelect={setFocusedVideoId}
                onTrigger={() => {}}
              />
              {status.suggestions.map((s) => {
                const videoId = suggestionVideoIds[s.id] === "pending" ? null : suggestionVideoIds[s.id] || s.video_id;
                return (
                  <QuestionChip
                    key={s.id}
                    label={s.question}
                    videoId={videoId}
                    active={false}
                    onSelect={setFocusedVideoId}
                    onTrigger={() => handleTriggerSuggestion(s.id)}
                    disabled={pendingSuggestionIds.has(s.id)}
                  />
                );
              })}
              {extraQuestions.map((q) => (
                <QuestionChip
                  key={q.videoId}
                  label={q.label}
                  videoId={q.videoId}
                  active={false}
                  onSelect={setFocusedVideoId}
                  onTrigger={() => {}}
                />
              ))}
            </div>

            <FollowupInput onSubmit={handleAskAndFocus} disabled={false} />
            {askError && <p className="panel-error">{askError}</p>}
          </>
        )}
      </div>
    </div>
  );
}

function FocusedView({ videoId, label, watching, onWatch, onBack }) {
  const { status } = useVideoStatus(videoId);
  const ready = status?.status === "done";
  const failed = status?.status === "error";

  return (
    <div className="explain-focused">
      <button type="button" className="explain-back-link" onClick={onBack}>
        ‹ Back
      </button>

      {watching && ready ? (
        <VideoPlayer src={videoFileUrl(videoId)} title={label} />
      ) : failed ? (
        <p className="panel-error">Video generation failed: {status.error}</p>
      ) : ready ? (
        <div className="explain-ready">
          <p className="explain-ready-title">{label}</p>
          <button type="button" className="explain-watch-button" onClick={onWatch}>
            ▶ Watch
          </button>
        </div>
      ) : (
        <div className="explain-generating">
          <span className="spinner" aria-hidden="true" />
          <p className="explain-generating-title">{label}</p>
          <p className="panel-status">{status?.stage_detail || status?.status || "Generating…"}</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add CSS**

```css
.explain-overlay-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 100;
}

.explain-overlay {
  position: relative;
  background: var(--panel-bg);
  border: 1px solid var(--border-strong);
  border-radius: 20px;
  box-shadow: var(--shadow);
  max-width: 560px;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  padding: 28px;
  transition: max-width 0.2s ease;
}

.explain-overlay.watching {
  max-width: 960px;
  max-height: 92vh;
}

.explain-overlay-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: var(--panel-bg-2);
  color: var(--text-muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.explain-overlay-close:hover {
  color: var(--text);
}

.explain-overlay-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 12px;
  padding-right: 28px;
}

.explain-overlay-title {
  font-weight: 700;
  font-size: 16px;
}

.explain-overlay-subtitle {
  font-size: 13px;
  color: var(--text-muted);
}

.explain-back-link {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 0 0 12px;
}

.explain-back-link:hover {
  color: var(--text);
}

.explain-generating,
.explain-ready {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
  padding: 32px 8px;
}

.explain-generating .spinner,
.explain-ready .spinner {
  width: 22px;
  height: 22px;
  border-width: 3px;
}

.explain-generating-title,
.explain-ready-title {
  font-size: 17px;
  font-weight: 700;
}

.explain-watch-button {
  border: none;
  background: var(--accent);
  color: var(--accent-contrast);
  border-radius: 999px;
  padding: 14px 28px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s ease;
}

.explain-watch-button:hover {
  background: var(--accent-hover);
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`

```bash
git add frontend/src/components/QuestionChip.jsx frontend/src/components/ExplainOverlay.jsx frontend/src/index.css
git commit -m "feat: add ExplainOverlay full-screen generating/ready/watch flow"
```

---

### Task 5: Wire everything into `SchdFundPage.jsx`

**Files:**
- Modify: `frontend/src/pages/SchdFundPage.jsx`

**Interfaces:**
- Consumes: `useTextSelection` (Task 1), `SelectionExplainButton` (Task 2), `ExplainEntryButton` (Task 3), `ExplainOverlay` (Task 4).

- [ ] **Step 1: Replace the `ExplainModule` mount and `contextualQuestion` state with the new overlay wiring**

```jsx
import { useState } from "react";
import DistributionHistory from "../components/DistributionHistory";
import ExplainEntryButton from "../components/ExplainEntryButton";
import ExplainOverlay from "../components/ExplainOverlay";
import FundDetailsTable from "../components/FundDetailsTable";
import OrderBox from "../components/OrderBox";
import PriceChart from "../components/PriceChart";
import SectorWeights from "../components/SectorWeights";
import SelectionExplainButton from "../components/SelectionExplainButton";
import TopHoldingsTable from "../components/TopHoldingsTable";
import VerifiedBadge from "../components/VerifiedBadge";
import WatchlistStar from "../components/WatchlistStar";
import Toast from "../components/Toast";
import { useTextSelection } from "../hooks/useTextSelection";
import { schdFund, schdFundContentText } from "../data/schdFund";

export default function SchdFundPage() {
  const [toastMessage, setToastMessage] = useState(null);
  const [explainOpen, setExplainOpen] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const { selection, clear: clearSelection } = useTextSelection();

  function handleTradeAction(label) {
    setToastMessage(`${label} isn't available in this demo`);
  }

  function handleSelectionExplain(text) {
    setPendingQuestion({
      prompt: `Explain what "${text}" means in the context of ${schdFund.name}.`,
      label: text,
    });
    setExplainOpen(true);
    clearSelection();
  }

  return (
    <div className="fund-page">
      <header className="fund-header">
        <div className="fund-header-top">
          <span className="fund-ticker">{schdFund.ticker}</span>
          <VerifiedBadge />
          <WatchlistStar />
        </div>
        <h1>{schdFund.name}</h1>
        <p className="fund-subhead">{schdFund.category}</p>

        <div className="hero-stats">
          <div className="hero-stat">
            <span className="hero-stat-value">{schdFund.expenseRatio}%</span>
            <span className="hero-stat-label">Expense ratio</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-value accent">{schdFund.distributionYieldPct}%</span>
            <span className="hero-stat-label">Dividend yield (TTM)</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-value">${schdFund.aumBillions}B</span>
            <span className="hero-stat-label">Net assets</span>
          </div>
        </div>

        <div className="chart-order-row">
          <PriceChart
            price={schdFund.price}
            dayChange={schdFund.dayChange}
            dayChangePct={schdFund.dayChangePct}
          />
          <OrderBox ticker={schdFund.ticker} onAction={handleTradeAction} />
        </div>
      </header>

      <FundDetailsTable fund={schdFund} />
      <TopHoldingsTable holdings={schdFund.topHoldings} />
      <DistributionHistory history={schdFund.distributionHistory} />
      <SectorWeights sectors={schdFund.sectorWeights} />

      <footer className="fund-footer">Illustrative demo data, not live market data.</footer>

      <Toast message={toastMessage} onDone={() => setToastMessage(null)} />

      <ExplainEntryButton onClick={() => setExplainOpen(true)} />
      {!explainOpen && <SelectionExplainButton selection={selection} onExplain={handleSelectionExplain} />}
      <ExplainOverlay
        fundContentText={schdFundContentText}
        open={explainOpen}
        onClose={() => setExplainOpen(false)}
        pendingQuestion={pendingQuestion}
        onPendingHandled={() => setPendingQuestion(null)}
      />
    </div>
  );
}
```

(`onExplain` is no longer passed to `FundDetailsTable`/`TopHoldingsTable`/`DistributionHistory` — that prop and the buttons that used it are removed in Task 6. The `SelectionExplainButton` is hidden while the overlay is open, so selecting text inside the overlay's own content doesn't pop up a redundant floating button on top of it.)

- [ ] **Step 2: Verify**

Run: `cd frontend && npm run lint && npm run build` — both should stay clean. This codebase has no prop-type checking, so `FundDetailsTable`/`TopHoldingsTable`/`DistributionHistory` still expecting an `onExplain` prop that's no longer passed is not a lint/build-time error — it's a transient *runtime* gap (their still-present "✨" buttons would call `undefined(...)` if clicked) that Task 6 closes immediately after by removing those buttons entirely. Don't "fix" it by leaving the old prop wiring in place on this side — Task 6 removes it from the other side.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SchdFundPage.jsx
git commit -m "feat: replace inline ExplainModule with overlay + highlight-to-explain entry points"
```

---

### Task 6: Revert the three table components (remove the now-redundant "✨" triggers)

**Files:**
- Modify: `frontend/src/components/FundDetailsTable.jsx`
- Modify: `frontend/src/components/TopHoldingsTable.jsx`
- Modify: `frontend/src/components/DistributionHistory.jsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: `FundDetailsTable.jsx`** — drop `onExplain` and the per-cell button

```jsx
export default function FundDetailsTable({ fund }) {
  const cells = [
    ["AUM", `$${fund.aumBillions}B`],
    ["Price-Earnings ratio", fund.peRatio],
    ["30-Day yield", `${fund.thirtyDayYieldPct}%`],
    ["Average volume", fund.avgVolume],
    ["High today", `$${fund.highToday.toFixed(2)}`],
    ["Low today", `$${fund.lowToday.toFixed(2)}`],
    ["Open price", `$${fund.openPrice.toFixed(2)}`],
    ["Volume", fund.volume],
    ["52 Week high", `$${fund.week52High.toFixed(2)}`],
    ["52 Week low", `$${fund.week52Low.toFixed(2)}`],
    ["Expense ratio", `${fund.expenseRatio}%`],
    ["Short inventory", fund.shortInventory],
    ["Borrow rate", `${fund.borrowRatePct.toFixed(2)}%`],
  ];

  return (
    <section className="fund-section">
      <h2>Key statistics</h2>
      <div className="stat-grid stat-grid-4">
        {cells.map(([label, value]) => (
          <div className="stat-cell" key={label}>
            <span className="stat-label">{label}</span>
            <span className="stat-value">{value}</span>
          </div>
        ))}
      </div>
      <a className="fund-details-link" href="#" onClick={(e) => e.preventDefault()}>
        View Prospectus and Reports
      </a>
    </section>
  );
}
```

- [ ] **Step 2: `TopHoldingsTable.jsx`** — drop `onExplain` and the per-row button

```jsx
export default function TopHoldingsTable({ holdings }) {
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
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: `DistributionHistory.jsx`** — drop `onExplain` and the per-row button

```jsx
export default function DistributionHistory({ history }) {
  return (
    <section className="fund-section">
      <h2>Recent distributions</h2>
      <div className="distribution-list">
        {history.map((d) => (
          <div className="distribution-row" key={d.exDate}>
            <span className="distribution-date">{d.exDate}</span>
            <span className="distribution-amount">+${d.amount.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Revert `.holding-row`'s grid columns** in `frontend/src/index.css` — the 4th column existed only for the removed trigger button

```css
.holding-row {
  display: grid;
  grid-template-columns: 120px 1fr 44px;
  align-items: center;
  gap: 14px;
}
```

- [ ] **Step 5: Verify and commit**

Run: `cd frontend && npm run lint && npm run build` — should be fully clean now (this closes out the intentional gap from Task 5).

```bash
git add frontend/src/components/FundDetailsTable.jsx frontend/src/components/TopHoldingsTable.jsx frontend/src/components/DistributionHistory.jsx frontend/src/index.css
git commit -m "refactor: remove redundant per-row explain triggers now that any text is selectable"
```

---

### Task 7: Delete `ExplainModule.jsx` and remove its now-dead CSS

**Files:**
- Delete: `frontend/src/components/ExplainModule.jsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Delete the file**

```bash
git rm frontend/src/components/ExplainModule.jsx
```

- [ ] **Step 2: Remove dead CSS rules**: `.explain-module`, `.explain-module-header`, `.explain-module-title`, `.explain-module-subtitle`, `.explain-trigger`, `.explain-trigger:hover`, `.stat-cell-label-row` (all superseded — the overlay uses `.explain-overlay*` from Task 4, and the per-row trigger buttons/wrapper are gone as of Task 6).

- [ ] **Step 3: Verify and commit**

Run: `cd frontend && npm run lint && npm run build`
Manual check: `grep -rn "ExplainModule\|explain-module\|explain-trigger\|stat-cell-label-row" frontend/src/` should return nothing.

```bash
git add -A
git commit -m "refactor: delete superseded ExplainModule and its dead CSS"
```

---

## Verification summary

Since no headless browser tool is available in this environment, verification is `npm run lint` + `npm run build` after every task, plus tracing the state machine by hand for each task's specific risk (Task 4's chip click/disable logic and the menu↔focused↔watching transitions in particular). The human partner should confirm the actual feel of it (blur, transitions, selection button positioning) in a real browser via the running dev server — call this out explicitly rather than claiming a visual result that wasn't actually seen.

**End-to-end flow to trace/confirm once all 7 tasks land:**
1. Load the page — no inline box, just the small `✨` entry button bottom-right.
2. Select any text on the page (e.g. a holding name) — a floating "✨ Explain this" pops up near the selection.
3. Click it — the page blurs behind a centered card showing live generation progress for that exact selected text.
4. Once done, the card shows a "▶ Watch" button instead of autoplaying.
5. Click Watch — the overlay expands and plays the video full-viewport-ish.
6. "‹ Back" steps back to the ready card; another "‹ Back" (from the menu-less focused view, since it was opened via selection not the menu) or "×" closes back to the normal page.
7. Click the persistent `✨` entry button instead — opens straight into the menu (base video chip + 3 suggestion chips + free-text input + any already-asked questions from this session), each clickable into its own focused view the same way.
8. Re-open the overlay later in the same session — anything already generated is still there (session/videos state persists across open/close since the component stays mounted).
