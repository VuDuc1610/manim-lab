const API_BASE = "http://localhost:5000";

async function request(path, options) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new Error(data?.error || `request failed: ${resp.status}`);
  }
  return data;
}

export function createSession(fundContent) {
  return request("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ fund_content: fundContent }),
  });
}

export function getSessionStatus(sessionId) {
  return request(`/api/sessions/${sessionId}`);
}

export function postFollowup(sessionId, question, grounded = true) {
  return request(`/api/sessions/${sessionId}/followup`, {
    method: "POST",
    body: JSON.stringify({ question, grounded }),
  });
}

export function generateSuggestion(sessionId, suggestionId) {
  return request(`/api/sessions/${sessionId}/suggestions/${suggestionId}/generate`, {
    method: "POST",
  });
}

export function getVideoStatus(videoId) {
  return request(`/api/videos/${videoId}/status`);
}

export function getHistory() {
  return request("/api/history");
}

export function videoFileUrl(videoId) {
  return `${API_BASE}/api/videos/${videoId}/file`;
}
