"use client";

import { useState, useTransition } from "react";

import { sendChatMessage, type ChatResponse } from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
  metadata?: ChatResponse;
};

const starterPrompts = [
  "Plan an Azure landing zone rollout with approval gates.",
  "Summarize the OMNIRA architecture and routing model.",
  "Help me design a safe Terraform workflow for local-first development.",
];

export function ChatClient() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "OMNIRA Prime is ready. Ask about architecture, code, memory, RAG, platform operations, or model routing.",
    },
  ]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const submitMessage = (message: string) => {
    if (!message.trim()) {
      return;
    }

    setError(null);
    setMessages((current) => [...current, { role: "user", content: message }]);
    setInput("");

    startTransition(async () => {
      try {
        const response = await sendChatMessage(message);
        setMessages((current) => [
          ...current,
          { role: "assistant", content: response.response, metadata: response },
        ]);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unknown chat error.");
      }
    });
  };

  return (
    <div className="flex min-h-[70vh] flex-col gap-6 rounded-[32px] border border-white/60 bg-white/70 p-5 shadow-panel backdrop-blur">
      <div className="grid gap-3 sm:grid-cols-3">
        {starterPrompts.map((prompt) => (
          <button
            className="rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left text-sm text-slate-700 transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-lg"
            key={prompt}
            onClick={() => submitMessage(prompt)}
            type="button"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-hidden rounded-[28px] border border-slate-200 bg-slate-950/95 p-4 text-slate-100">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <p className="text-xs uppercase tracking-[0.26em] text-sky-300">Live Session</p>
            <p className="mt-1 text-lg font-semibold">OMNIRA Prime Chat</p>
          </div>
          <p className="rounded-full border border-sky-400/30 bg-sky-400/10 px-3 py-1 text-xs text-sky-200">
            {isPending ? "Thinking" : "Ready"}
          </p>
        </div>

        <div className="flex max-h-[48vh] flex-1 flex-col gap-4 overflow-y-auto pr-1">
          {messages.map((message, index) => (
            <div
              className={message.role === "user" ? "self-end" : "self-start"}
              key={`${message.role}-${index}`}
            >
              <div
                className={
                  message.role === "user"
                    ? "max-w-2xl rounded-[24px] rounded-br-md bg-sky-400 px-4 py-3 text-sm text-slate-950"
                    : "max-w-2xl rounded-[24px] rounded-bl-md bg-slate-900 px-4 py-3 text-sm text-slate-100 ring-1 ring-white/10"
                }
              >
                <p className="whitespace-pre-wrap leading-6">{message.content}</p>
                {message.metadata ? (
                  <div className="mt-3 grid gap-2 border-t border-white/10 pt-3 text-xs text-slate-300 sm:grid-cols-2">
                    <span>Model: {message.metadata.model}</span>
                    <span>Agent: {message.metadata.agent}</span>
                    <span>Provider: {message.metadata.provider}</span>
                    <span>Flags: {message.metadata.safety_flags.join(", ") || "none"}</span>
                  </div>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        <form
          className="grid gap-3 rounded-[24px] border border-white/10 bg-slate-900/80 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            submitMessage(input);
          }}
        >
          <textarea
            className="min-h-28 rounded-[20px] border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-sky-400/50"
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask OMNIRA to route, recall, research, or plan."
            value={input}
          />
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <p className="text-xs text-slate-400">
              Responses display the selected model and agent metadata from the backend.
            </p>
            <button
              className="rounded-full bg-gradient-to-r from-sky-300 via-cyan-300 to-emerald-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isPending}
              type="submit"
            >
              {isPending ? "Routing..." : "Send to OMNIRA Prime"}
            </button>
          </div>
          {error ? <p className="text-sm text-orange-300">{error}</p> : null}
        </form>
      </div>
    </div>
  );
}
