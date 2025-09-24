// API utilities for backend interaction (JSON + SSE streaming)
import { performLogout } from "./logout";
const API_URL = process.env.NEXT_PUBLIC_API_URL

const MAX_ATTEMPTS = 10;
const BACKOFF_BASE_MS = 300;

function delay(ms: number) {
  return new Promise((res) => setTimeout(res, ms));
}

function messagesToMarkdown(messages: any[]): string {
  const mdParts: string[] = ["# Chat history\n\n"];
  for (const m of messages) {
    const t = m?.createdAt ? new Date(m.createdAt).toISOString() : "";
    const sender = m?.sender || "user";
    mdParts.push(`**${sender}** - ${t}\n\n`);
    mdParts.push((m?.text || "") + "\n\n---\n\n");
  }
  return mdParts.join("");
}

function getAccessToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function getRefreshToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

async function tryRefresh() {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_URL}/api/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data?.access) {
      localStorage.setItem("access_token", data.access);
      return true;
    }
  } catch (e) {
    console.warn("refresh failed", e);
  }
  return false;
}

export { tryRefresh };

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  let token = getAccessToken();

  // Special-case: if this is the download endpoint and caller passed JSON messages,
  // convert messages => markdown and send as text/markdown to backend.
  const normalizedEndpoint = endpoint || "";
  const isDownloadEndpoint = /download-chat-md\/?$/.test(normalizedEndpoint);
  let bodyToSend: any = options.body;
  let headers = { ...(options.headers || {}) } as Record<string, any>;

  if (isDownloadEndpoint) {
    try {
      // if body is a JSON-string with { messages }
      if (typeof options.body === "string") {
        const parsed = JSON.parse(options.body);
        if (parsed && Array.isArray(parsed.messages)) {
          bodyToSend = messagesToMarkdown(parsed.messages);
          headers["Content-Type"] = "text/markdown";
        }
      } else if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
        const maybe = options.body as any;
        if (maybe.messages && Array.isArray(maybe.messages)) {
          bodyToSend = messagesToMarkdown(maybe.messages);
          headers["Content-Type"] = "text/markdown";
        }
      }
    } catch (e) {
      // fallback: leave body as-is
    }
  } else {
    // For non-download calls, if body is present and not FormData, ensure JSON content-type
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
  }

  // If body is a plain object and not FormData, stringify it for fetch
  if (bodyToSend && !(bodyToSend instanceof FormData) && typeof bodyToSend !== "string") {
    try {
      bodyToSend = JSON.stringify(bodyToSend);
    } catch (e) {
      // leave as-is
    }
  }

  let lastErr: any = null;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const res = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        body: bodyToSend,
        headers: {
          ...headers,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      console.log("apiFetch raw response", res, "attempt", attempt);

      // Auth errors: try refresh once (not counted as a separate attempt)
      if (res.status === 401 || res.status === 403) {
        const ok = await tryRefresh();
        if (ok) {
          token = getAccessToken();
          // retry immediately with refreshed token
          const retried = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            body: bodyToSend,
            headers: {
              ...headers,
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
          });
          if (!retried.ok) {
            // If retried failed with auth again, logout
            if (retried.status === 401 || retried.status === 403) {
              performLogout("/");
              return;
            }
            // If server error, allow retry loop to continue
            if (retried.status >= 500 && attempt < MAX_ATTEMPTS) {
              lastErr = new Error(`HTTP ${retried.status}`);
              await delay(BACKOFF_BASE_MS * attempt);
              continue;
            }
            // For other errors, parse and throw
            const ct = retried.headers.get("content-type") || "";
            if (ct.includes("application/json")) {
              const json = await retried.json().catch(() => ({}));
              if (json && typeof json === "object" && json.detail && /Authentication credentials were not provided\./i.test(String(json.detail))) {
                performLogout("/");
                return;
              }
              throw new Error(typeof json === "string" ? json : JSON.stringify(json));
            } else {
              const text = await retried.text().catch(() => "");
              if (/Authentication credentials were not provided\./i.test(text)) {
                performLogout("/");
                return;
              }
              throw new Error(text || `HTTP ${retried.status}`);
            }
          }
          // success on refreshed retry
          const ct2 = retried.headers.get("content-type") || "";
          if (ct2.includes("application/json")) return retried.json();
          return retried.text();
        } else {
          performLogout("/");
          return;
        }
      }

      if (!res.ok) {
        // Retry on server errors (5xx)
        if (res.status >= 500 && attempt < MAX_ATTEMPTS) {
          lastErr = new Error(`HTTP ${res.status}`);
          await delay(BACKOFF_BASE_MS * attempt);
          continue;
        }

        const ct = res.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          const json = await res.json().catch(() => ({}));
          if (json && typeof json === "object" && json.detail && /Authentication credentials were not provided\./i.test(String(json.detail))) {
            performLogout("/");
            return;
          }
          throw new Error(typeof json === "string" ? json : JSON.stringify(json));
        } else {
          const text = await res.text().catch(() => "");
          if (/Authentication credentials were not provided\./i.test(text)) {
            performLogout("/");
            return;
          }
          throw new Error(text || `HTTP ${res.status}`);
        }
      }

      const ct = res.headers.get("content-type") || "";
      if (ct.includes("application/json")) return res.json();
      return res.text();
    } catch (err: any) {
      // network / parsing errors
      lastErr = err;
      if (attempt < MAX_ATTEMPTS) {
        await delay(BACKOFF_BASE_MS * attempt);
        continue;
      }
      // final failure
      throw err;
    }
  }
  // If we exit loop unexpectedly
  throw lastErr || new Error("Request failed after retries");
}

// Stream agents pipeline via SSE over fetch (works with auth headers)
export type AgentsStreamHandlers = {
  onEvent?: (evt: any) => void; // raw parsed SSE JSON from backend "data: ..."
  onError?: (err: Error) => void;
  onDone?: () => void;
};

export function streamAgents(payload: any, handlers: AgentsStreamHandlers = {}) {
  const { onEvent, onError, onDone } = handlers;
  const token = getAccessToken();
  const controller = new AbortController();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  (async () => {
    try {
      let res: Response | null = null;
      let lastErr: any = null;
      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        const tokenNow = getAccessToken();
        try {
          res = await fetch(`${API_URL}/api/agents/`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(tokenNow ? { Authorization: `Bearer ${tokenNow}` } : {}),
            },
            body: JSON.stringify(payload),
            signal: controller.signal,
          });
        } catch (err) {
          lastErr = err;
          if (attempt < MAX_ATTEMPTS) {
            await delay(BACKOFF_BASE_MS * attempt);
            continue;
          }
          onError?.(err instanceof Error ? err : new Error(String(err)));
          onDone?.();
          return;
        }

        if (res.ok) break;

        // Handle auth errors by attempting refresh, then retrying
        if (res.status === 401 || res.status === 403) {
          const refreshed = await tryRefresh();
          if (refreshed) {
            // retry immediately (counts as another attempt)
            if (attempt < MAX_ATTEMPTS) {
              await delay(0);
              continue;
            } else {
              console.warn("streamAgents: refreshed but reached max attempts");
              performLogout("/");
              return;
            }
          } else {
            console.warn("streamAgents: auth error status", res.status, "-> logout");
            performLogout("/");
            return;
          }
        }

        // Retry on server errors
        if (res.status >= 500 && attempt < MAX_ATTEMPTS) {
          lastErr = new Error(`HTTP ${res.status}`);
          await delay(BACKOFF_BASE_MS * attempt);
          continue;
        }

        // Non-retryable error
        onError?.(new Error(`HTTP ${res.status}`));
        onDone?.();
        return;
      }

      if (!res) {
        onError?.(new Error("No response from server"));
        onDone?.();
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError?.(new Error("No readable stream from response"));
        onDone?.();
        return;
      }

      // Parse SSE: split on double newlines; process lines starting with 'data:'
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let parts = buffer.split(/\n\n/);
        buffer = parts.pop() || "";
        for (const part of parts) {
          const lines = part.split(/\n/).map(l => l.trim());
          for (const line of lines) {
            if (line.startsWith("data:")) {
              const jsonStr = line.slice(5).trim();
              if (!jsonStr) continue;
              try {
                const evt = JSON.parse(jsonStr);
                onEvent?.(evt);
              } catch (e) {
                // ignore parse error but notify
                onError?.(new Error("Failed to parse SSE data"));
              }
            }
          }
        }
      }
      // Flush leftover buffer (if any complete data line)
      if (buffer.includes("data:")) {
        try {
          const last = buffer.trim().split(/\n/).find(l => l.startsWith("data:"));
          if (last) onEvent?.(JSON.parse(last.slice(5).trim()));
        } catch {}
      }
      onDone?.();
    } catch (err: any) {
      if (err?.name === "AbortError") return; // cancelled
      onError?.(err instanceof Error ? err : new Error(String(err)));
      onDone?.();
    }
  })();

  return {
    cancel: () => controller.abort(),
  };
}

export async function getAgentsLast() {
  return apiFetch("/api/agents/");
}

export async function deleteAgentsCache() {
  return apiFetch("/api/agents/cache/", { method: "DELETE" });
}
