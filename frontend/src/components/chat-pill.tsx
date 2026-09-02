"use client";

import { AlertTriangle, MessageCircle, Send, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The helper: a pill bottom-right that opens a chat panel.
 *
 * Two things this deliberately does NOT do:
 *  - It never renders a verdict of its own. When the assistant consults the
 *    engine, a tool_use event arrives and we show that the official check ran,
 *    with its verdict, styled as the verdict tokens — not as chat prose.
 *  - It never shows a policy claim without its source. Citation chips come from
 *    the stream and link to the citation record.
 */

type Citation = { citation_id: string; is_unverified: boolean };

type Message = {
  role: "user" | "assistant";
  text: string;
  citations: Citation[];
  verdict?: string | null;
  error?: string;
  /** Identifiers the server stripped out of this question before sending it. */
  scrubbed?: string[];
};

const SCRUB_LABELS: Record<string, string> = {
  national_id: "ID number",
  phone: "phone number",
  email: "email address",
};

const SUGGESTIONS = [
  "What do I need to bring to the depot?",
  "How many bags can I get for 3 acres?",
  "Nahitaji nini ili nipate mbolea?",
];

export function ChatPill() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;

    setDraft("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", text, citations: [] },
      { role: "assistant", text: "", citations: [] },
    ]);

    const patchLast = (patch: (message: Message) => Message) =>
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = patch(next[next.length - 1]);
        return next;
      });

    try {
      const response = await fetch("/api/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, conversationId, locale: /[a-z]/.test(text) ? "en" : "en" }),
      });

      if (!response.body) throw new Error("no stream");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line.
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          let event = "message";
          let data = "";
          for (const line of frame.split("\n")) {
            if (line.startsWith("event: ")) event = line.slice(7).trim();
            else if (line.startsWith("data: ")) data += line.slice(6);
          }
          if (!data) continue;

          let payload: Record<string, unknown>;
          try {
            payload = JSON.parse(data);
          } catch {
            continue;
          }

          if (event === "message_start") {
            if (typeof payload.conversation_id === "string") {
              setConversationId(payload.conversation_id);
            }
            if (typeof payload.signed_in === "boolean") {
              setSignedIn(payload.signed_in);
            }
          } else if (event === "scrubbed") {
            // Shown on the farmer's own message: the identifier they typed was
            // removed here and never sent on.
            const kinds = Array.isArray(payload.kinds) ? (payload.kinds as string[]) : [];
            setMessages((prev) => {
              const next = [...prev];
              const mine = next.length - 2;
              if (mine >= 0) next[mine] = { ...next[mine], scrubbed: kinds };
              return next;
            });
          } else if (event === "text" && typeof payload.delta === "string") {
            const delta = payload.delta;
            patchLast((m) => ({ ...m, text: m.text + delta }));
          } else if (event === "citation") {
            const citation = payload as unknown as Citation;
            patchLast((m) =>
              m.citations.some((c) => c.citation_id === citation.citation_id)
                ? m
                : { ...m, citations: [...m.citations, citation] },
            );
          } else if (event === "tool_use" && payload.verdict) {
            patchLast((m) => ({ ...m, verdict: String(payload.verdict) }));
          } else if (event === "error") {
            patchLast((m) => ({ ...m, error: String(payload.message ?? "Something went wrong.") }));
          }
        }
      }
    } catch {
      patchLast((m) => ({
        ...m,
        error: "The helper is unavailable. The depot check still works.",
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {/* The pill */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Close the helper" : "Open the helper"}
        className={cn(
          "fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full",
          "bg-primary text-primary-foreground shadow-lg",
          "px-5 py-4 text-base font-heading tracking-wide",
          // Big target: this is used on a low-end phone, one-handed.
          "min-h-14 transition-transform hover:scale-[1.03] focus-visible:outline-2",
          "focus-visible:outline-offset-2 focus-visible:outline-statutory-strong",
          open && "scale-95",
        )}
      >
        {open ? <X className="size-5" aria-hidden /> : <MessageCircle className="size-5" aria-hidden />}
        <span>{open ? "Close" : "Ask for help"}</span>
      </button>

      {/* The panel */}
      {open && (
        <section
          role="dialog"
          aria-label="Kilimo Hakika helper"
          className={cn(
            "fixed z-50 flex flex-col overflow-hidden border border-border bg-card shadow-2xl",
            // Full-height sheet on a phone, a panel on a desktop.
            "inset-x-0 bottom-0 top-0 rounded-none",
            "sm:inset-auto sm:bottom-24 sm:right-5 sm:top-auto sm:h-[34rem] sm:w-[26rem] sm:rounded-xl",
          )}
        >
          <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
            <div>
              <h2 className="font-heading text-lg leading-tight">Helper</h2>
              <p className="text-muted-foreground text-xs">
                Explains the rules and cites the source. It never decides your verdict.
              </p>
              {signedIn === false && (
                <p className="text-muted-foreground mt-1 text-xs">
                  Answering general questions about the rules. Sign in for your own depot
                  check and your saved history.
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close the helper"
              className="text-muted-foreground hover:text-foreground rounded p-1"
            >
              <X className="size-5" aria-hidden />
            </button>
          </header>

          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-muted-foreground text-sm">
                  Ask about the documents you need, the official cap, or the gazetted price.
                </p>
                <div className="flex flex-col gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => ask(suggestion)}
                      className="border-border hover:bg-muted rounded-md border px-3 py-2 text-left text-sm"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, index) => (
              <div
                key={index}
                className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={cn(
                    "max-w-[85%] space-y-2 rounded-lg px-3 py-2 text-sm",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground",
                  )}
                >
                  {message.verdict && (
                    <div
                      className={cn(
                        "flex items-center gap-2 rounded border px-2 py-1 text-xs font-heading",
                        message.verdict === "PROCEED"
                          ? "border-proceed text-proceed"
                          : "border-gate text-gate",
                      )}
                    >
                      <ShieldCheck className="size-3.5" aria-hidden />
                      <span>
                        Official check ran:{" "}
                        {message.verdict === "PROCEED" ? "Proceed" : "Do not travel"}
                      </span>
                    </div>
                  )}

                  {message.text && <p className="whitespace-pre-wrap">{message.text}</p>}

                  {!message.text && !message.error && message.role === "assistant" && busy && (
                    <p className="text-muted-foreground italic">Checking the rules…</p>
                  )}

                  {message.error && (
                    <p className="text-gate flex items-start gap-2">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                      <span>{message.error}</span>
                    </p>
                  )}

                  {message.scrubbed && message.scrubbed.length > 0 && (
                    <p className="flex items-start gap-1.5 text-[0.7rem] opacity-90">
                      <ShieldCheck className="mt-0.5 size-3 shrink-0" aria-hidden />
                      <span>
                        Your{" "}
                        {message.scrubbed
                          .map((kind) => SCRUB_LABELS[kind] ?? kind)
                          .join(" and ")}{" "}
                        was removed and not sent. You never need it here.
                      </span>
                    </p>
                  )}

                  {message.citations.length > 0 && (
                    <ul className="flex flex-wrap gap-1 pt-1">
                      {message.citations.map((citation) => (
                        <li key={citation.citation_id}>
                          <span
                            className={cn(
                              "inline-block rounded border px-1.5 py-0.5 text-[0.65rem]",
                              citation.is_unverified
                                ? "border-gate/50 text-gate"
                                : "border-border text-muted-foreground",
                            )}
                            title={
                              citation.is_unverified
                                ? "Not traced to a gazette notice or circular"
                                : "Official source"
                            }
                          >
                            {citation.citation_id}
                            {citation.is_unverified && " · unverified"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ))}
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              ask(draft);
            }}
            className="border-border flex items-center gap-2 border-t px-3 py-3"
          >
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask a question…"
              aria-label="Your question"
              className={cn(
                "border-input bg-background min-h-11 flex-1 rounded-md border px-3 text-sm",
                "focus-visible:outline-statutory-strong focus-visible:outline-2 focus-visible:outline-offset-1",
              )}
            />
            <Button type="submit" size="lg" disabled={busy || !draft.trim()} aria-label="Send">
              <Send className="size-4" aria-hidden />
            </Button>
          </form>
        </section>
      )}
    </>
  );
}
