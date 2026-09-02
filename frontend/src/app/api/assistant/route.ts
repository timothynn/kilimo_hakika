import { apiBaseUrl } from "@/lib/kilimo-api";
import { getServiceToken, grantConsent } from "@/lib/kilimo-session";

export const runtime = "nodejs";

/**
 * Streams the assistant through this server so the service token never reaches
 * the browser. The upstream Server-Sent Event stream is passed through
 * unchanged — text deltas, citations, tool_use and done all arrive in order.
 */
export async function POST(request: Request) {
  const base = apiBaseUrl();
  if (!base) {
    return sse({
      code: "ASSISTANT_UNAVAILABLE",
      message: "The helper is not configured. Set KILIMO_API_URL.",
    });
  }

  // No token is not an error. A signed-out visitor gets the public tier of the
  // helper: it explains what the app does and what the rules require, and has
  // no tool that can reach anything personal. Signing in widens it.
  const token = await getServiceToken();

  let body: { text?: string; conversationId?: string | null; locale?: string };
  try {
    body = await request.json();
  } catch {
    return sse({ code: "INVALID_INPUT", message: "Expected a JSON body." });
  }
  const text = (body.text ?? "").trim();
  if (!text) {
    return sse({ code: "INVALID_INPUT", message: "Type a question first." });
  }

  const send = (extraHeaders: Record<string, string> = {}) =>
    fetch(`${base}/api/v1/assistant/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Omitted entirely when signed out — the service reads the absence of a
        // token as "visitor", not as a failed authentication.
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...extraHeaders,
      },
      body: JSON.stringify({
        text,
        conversation_id: body.conversationId ?? null,
        locale: body.locale === "sw" ? "sw" : "en",
      }),
      cache: "no-store",
    });

  let upstream = await send();

  // First use: the service refuses until ASSISTANT_AI consent exists. Record it
  // once and retry, rather than making the farmer hit send twice.
  if (upstream.status === 403) {
    const detail = await upstream
      .clone()
      .json()
      .catch(() => null);
    if (detail?.detail?.error?.code === "CONSENT_REQUIRED") {
      if (await grantConsent("ASSISTANT_AI")) {
        upstream = await send();
      }
    }
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.json().catch(() => null);
    return sse({
      code: detail?.detail?.error?.code ?? "ASSISTANT_UNAVAILABLE",
      message:
        detail?.detail?.error?.message ??
        "The helper is unavailable. The depot check still works.",
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

/** A one-event error stream, so the client has a single code path. */
function sse(error: { code: string; message: string }): Response {
  const payload = `event: error\ndata: ${JSON.stringify(error)}\n\n`;
  return new Response(payload, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store" },
  });
}
