"use client";

import React from "react";
import { apiFetch } from "../services/api";

interface MenuProps {
  minimized: boolean;
  setMinimized: (m: boolean) => void;
  username?: string | null;
  onRequestLogout?: () => void;
}

const Menu: React.FC<MenuProps> = ({ minimized, setMinimized, username, onRequestLogout }) => {
  if (minimized) return null;

  const apiUrl = `${process.env.NEXT_PUBLIC_API_URL}/api/core/apikeys/`;
  // single source of truth: usage comes from agents API cache or SSE usage events
  const usageApi = `${process.env.NEXT_PUBLIC_API_URL}/api/core/usage/`;
  const agentsApi = `${process.env.NEXT_PUBLIC_API_URL}/api/agents/`;
  const getToken = () => localStorage.getItem("access_token");

  const [usage, setUsage] = React.useState<{
    max_chats: number;
    max_gb: number;
    chats_used_today: number;
    used_bytes: number;
    max_bytes: number;
    seconds_until_reset: number;
  } | null>(null);

  // countdown to usage reset (server-provided). We'll store seconds_until_reset and optionally server_time
  const [countdown, setCountdown] = React.useState<string>('-');
  // internal state to keep remaining seconds (derived from server seconds_until_reset)
  const [remainingSeconds, setRemainingSeconds] = React.useState<number | null>(null);

  React.useEffect(() => {
    // live tick: decrement remainingSeconds if present
    const tick = () => {
      setRemainingSeconds((s) => {
        if (s == null) return s;
        const ns = Math.max(0, s - 1);
        return ns;
      });
    };
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, []);

  // format remainingSeconds into readable countdown
  React.useEffect(() => {
    if (remainingSeconds == null) {
      setCountdown('-');
      return;
    }
    const sec = Math.max(0, Math.floor(remainingSeconds || 0));
    const days = Math.floor(sec / (24 * 3600));
    const hrs = Math.floor((sec % (24 * 3600)) / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    const secs = sec % 60;
    setCountdown(`${days}d ${hrs}h ${mins}m ${secs}s`);
  }, [remainingSeconds]);

  React.useEffect(() => {
    const token = getToken();
    if (!token) return;
    let mounted = true;
    // Initialize from local cache first
    try {
      const cached = localStorage.getItem("usage_cache");
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed && mounted) {
          setUsage(parsed);
          if (typeof parsed.seconds_until_reset === 'number') setRemainingSeconds(Math.max(0, Math.floor(parsed.seconds_until_reset)));
        }
      }
    } catch (e) {
      // ignore parse errors
    }

    // Try to fetch recent cached agents result which may include usage in the same response
    const fetchFromAgentsCache = async () => {
      try {
        const res = await fetch(agentsApi, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) {
          // fallback to dedicated usage endpoint
          const ures = await fetch(usageApi, { headers: { Authorization: `Bearer ${token}` } });
          if (!ures.ok) return;
          const udata = await ures.json();
          if (!mounted) return;
          setUsage(udata);
          try { localStorage.setItem("usage_cache", JSON.stringify(udata)); } catch {}
          if (typeof udata.seconds_until_reset === 'number') setRemainingSeconds(Math.max(0, Math.floor(udata.seconds_until_reset)));
          return;
        }
        const data = await res.json();
        // agents GET returns { result, usage } since backend now caches usage
        const u = data?.usage || data;
        if (u && mounted) {
          setUsage(u);
          try { localStorage.setItem("usage_cache", JSON.stringify(u)); } catch {}
          if (typeof u.seconds_until_reset === 'number') setRemainingSeconds(Math.max(0, Math.floor(u.seconds_until_reset)));
        }
      } catch (e) {
        // network failure: fallback to usage endpoint
        try {
          const ures = await fetch(usageApi, { headers: { Authorization: `Bearer ${token}` } });
          if (!ures.ok) return;
          const udata = await ures.json();
          if (!mounted) return;
          setUsage(udata);
          try { localStorage.setItem("usage_cache", JSON.stringify(udata)); } catch {}
          if (typeof udata.seconds_until_reset === 'number') setRemainingSeconds(Math.max(0, Math.floor(udata.seconds_until_reset)));
        } catch (_) {}
      }
    };

    // initial fetch attempt
    fetchFromAgentsCache();

    // listen for usage updates dispatched elsewhere (e.g. SSE stream or agents cache update)
    const onUsageUpdated = (e: any) => {
      try {
        const d = e?.detail;
        if (d) {
          setUsage(d);
          try { localStorage.setItem("usage_cache", JSON.stringify(d)); } catch {}
          if (typeof d.seconds_until_reset === 'number') setRemainingSeconds(Math.max(0, Math.floor(d.seconds_until_reset)));
        }
      } catch (_) {}
    };
    window.addEventListener("usage_updated", onUsageUpdated as EventListener);

    // no need to poll here — countdown handled by remainingSeconds and SSE events.
    const interval = setInterval(() => {}, 1000);

    return () => {
      mounted = false;
      clearInterval(interval);
      window.removeEventListener("usage_updated", onUsageUpdated as EventListener);
    };
  }, []);

  const updateApiKey = async (value: string) => {
    setApiKeyLoading(true);
    const token = getToken();
    if (!token) {
      setApiKeyLoading(false);
      alert("Unauthorized, please login again.");
      localStorage.removeItem("access_token");
      onRequestLogout?.();
      window.location.href = "/";
      return;
    }

    try {
      const res = await fetch(apiUrl, {
        method: "POST", // DRF ViewSet.create
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ key: value }),
      });

      if (res.status === 401) {
        setApiKeyLoading(false);
        alert("Session expired, please login again.");
        localStorage.removeItem("access_token");
        onRequestLogout?.();
        window.location.href = "/";
        return;
      }

      const result = await res.json().catch(() => ({}));
      console.log("API key update response:", result);

      if (res.ok) {
        alert(value ? "API key updated successfully." : "API key cleared successfully.");
      } else {
        alert("Failed to update API key.");
      }
      setApiKeyLoading(false);
    } catch (err) {
      console.error("API key update error:", err);
      alert("Network error while updating API key.");
      setApiKeyLoading(false);
    }
  };

  const addOrReplaceKey = async () => {
    const key = prompt("Insert new API key:");
    if (key !== null) {
      await updateApiKey(key);
    }
  };

  const clearKey = async () => {
    if (window.confirm("Are you sure you want to clear the chatGPT API key?")) {
      await updateApiKey("");
    }
  };

  // Local UI loading flags
  const [apiKeyLoading, setApiKeyLoading] = React.useState(false);
  const [downloadLoading, setDownloadLoading] = React.useState(false);

  const fmtHMS = (s: number) => {
    const sec = Math.max(0, Math.floor(s || 0));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const ss = sec % 60;
    return `${h}h ${m}m ${ss}s`;
  };

  return (
    <div className="flex flex-col gap-4">
      {/* User info + logout/minimize */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-full bg-violet-600 text-white grid place-items-center text-xs">
            {(username?.[0] || "?").toUpperCase()}
          </div>
          <div className="truncate">
            <div className="text-sm font-medium truncate" title={username || undefined}>
              {username || "User"}
            </div>
          </div>
        </div>
        {/* empty space reserved for bottom usage card */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              // Open logout confirmation (actual clearing happens in performLogout)
              onRequestLogout?.();
            }}
            className="inline-flex items-center gap-1 rounded-full h-8 px-3 text-xs font-medium text-gray-100 bg-gray-800/70 hover:bg-gray-800/90 border border-white/10 shadow-sm backdrop-blur-md transition-colors"
            title="Logout"
            aria-label="Logout"
          >
            <svg
              className="w-3.5 h-3.5 text-gray-300"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Logout</span>
          </button>
          <button
            onClick={() => setMinimized(true)}
            className="inline-flex items-center gap-1 rounded-full h-8 px-3 text-xs font-medium text-gray-100 bg-gray-800/70 hover:bg-gray-800/90 border border-white/10 shadow-sm backdrop-blur-md transition-colors"
            title="Minimize menu"
            aria-label="Minimize menu"
          >
            <svg
              className="w-3.5 h-3.5 text-gray-300"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Hide</span>
          </button>
        </div>
      </div>

      {/* Clear chat session */}
      <button
        className="w-full px-3 py-2 mt-2 rounded bg-red-600 text-white text-xs font-medium hover:bg-red-700"
        onClick={() => {
          if (window.confirm("Are you sure you want to clear the chat session?")) {
            localStorage.removeItem("chatbot_messages");
            window.location.reload();
          }
        }}
      >
        Clear chat session
      </button>

      {/* API actions */}
      <div className="flex flex-col gap-2 mt-2">
        <button
          className="w-full px-3 py-2 rounded bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-70"
          onClick={addOrReplaceKey}
          disabled={apiKeyLoading}
        >
          {apiKeyLoading ? 'Working...' : 'Add/Replace chatGPT API key'}
        </button>
        <button
          className="w-full px-3 py-2 rounded bg-gray-600 text-white text-xs font-medium hover:bg-gray-700 disabled:opacity-70"
          onClick={clearKey}
          disabled={apiKeyLoading}
        >
          {apiKeyLoading ? 'Working...' : 'Clear chatGPT API key'}
        </button>
      </div>

      {/* Extra actions */}
      <div className="mt-8" />

      {/* Usage card (bottom) */}
      <div className="mb-16">
        <div className="rounded-lg bg-gray-800/60 border border-white/10 p-3 text-sm text-gray-200">
          <div className="font-medium mb-1">Usage</div>
          {usage ? (
            <div className="grid grid-cols-1 gap-1">
              <div>Chats: <span className="font-semibold">{usage.chats_used_today}</span> / <span className="text-gray-300">{usage.max_chats}</span></div>
              <div>Count down to reset Usage: <span className="font-semibold">{countdown}</span></div>
            </div>
          ) : (
            <div className="text-gray-400">Loading usage...</div>
          )}
        </div>
      </div>
      <button
        className="w-full px-3 py-2 rounded bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 mt-8"
        onClick={() => {
          window.open("/view-files", "_blank");
        }}
      >
        View/Import/Delete Databases
      </button>
        <button
          className="w-full px-3 py-2 rounded bg-yellow-600 text-white text-xs font-medium hover:bg-yellow-700 mt-3 disabled:opacity-70"
          onClick={async () => {
            setDownloadLoading(true);
            try {
              const raw = localStorage.getItem("chatbot_messages") || "[]";
              const messages = JSON.parse(raw);
              // Use apiFetch which attempts refresh automatically
              try {
                const text = await apiFetch("/api/core/download-chat-md/", { method: "POST", body: JSON.stringify({ messages, filename: `chat_${Date.now()}.md` }) });
                if (typeof text === "string") {
                  const blob = new Blob([text], { type: "text/markdown" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `chat_${Date.now()}.md`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  URL.revokeObjectURL(url);
                  setDownloadLoading(false);
                  return;
                }
              } catch (e) {
                // ignore and fallback to client generation
              }

              // fallback local generation
              const mdParts: string[] = ["# Chat history\n\n"];
              for (const m of messages) {
                const t = m.createdAt ? new Date(m.createdAt).toISOString() : "";
                mdParts.push(`**${m.sender || 'user'}** - ${t}\n\n`);
                mdParts.push((m.text || "") + "\n\n---\n\n");
              }
              const blob = new Blob([mdParts.join("")], { type: "text/markdown" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `chat_${Date.now()}.md`;
              document.body.appendChild(a);
              a.click();
              a.remove();
              URL.revokeObjectURL(url);
            } catch (e) {
              alert("Failed to download chat history: " + String(e));
            } finally {
              setDownloadLoading(false);
            }
          }}
          disabled={downloadLoading}
        >
          {downloadLoading ? 'Preparing...' : 'Download chat history (MD)'}
        </button>
    </div>
  );
};

export default Menu;
