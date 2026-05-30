import { useEffect, useState, useTransition } from "react";
import { loadJarvisState, sendJarvisMessage, type ChatResponse, type JarvisState } from "./lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
  meta?: string;
};

const starterPrompts = [
  "Hi good morning",
  "Jarvis what is the time",
  "Find files named README",
  "Search web for OMNIRA AI",
];

export default function App() {
  const [state, setState] = useState<JarvisState | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Jarvis Commander is online. Speak naturally or use the compact terminal when needed." },
  ]);
  const [input, setInput] = useState("");
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    loadJarvisState().then(setState).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const submit = async (message: string) => {
    const normalized = message.trim();
    if (!normalized) return;
    setMessages((current: Message[]) => [...current, { role: "user", content: normalized }]);
    setInput("");
    setError(null);
    try {
      const response: ChatResponse = await sendJarvisMessage(normalized, "C:/Users/vivek.rai/Project OM/omnira-ai");
      startTransition(() => {
        setMessages((current: Message[]) => [
          ...current,
          { role: "assistant", content: response.response, meta: response.intent || response.action || response.agent },
        ]);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <main className="shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <span className="eyebrow">Jarvis Commander</span>
          <h1>Voice-first AI commander with a cinematic desktop shell.</h1>
          <p>
            Fast assistant-core replies, approval-aware actions, and OMNIRA reasoning in one desktop surface.
          </p>
          <div className="chip-row">
            <span className="chip">{state?.listen.enabled ? "Live Listen On" : "Push To Talk"}</span>
            <span className="chip">{state?.capture.provider ?? "No STT"}</span>
            <span className="chip">{isPending ? "Thinking" : "Ready"}</span>
          </div>
        </div>
        <div className="orbital-core" aria-hidden="true">
          <div className="ring ring-a" />
          <div className="ring ring-b" />
          <div className="core" />
          <div className="pulse pulse-a" />
          <div className="pulse pulse-b" />
        </div>
      </section>

      <section className="command-bar">
        {starterPrompts.map((prompt) => (
          <button key={prompt} className="command-chip" onClick={() => submit(prompt)} type="button">
            {prompt}
          </button>
        ))}
      </section>

      <section className="conversation-panel">
        <header>
          <div>
            <p className="eyebrow">Assistant Channel</p>
            <h2>Holistic PA + AI Commander</h2>
          </div>
          <button className="terminal-toggle" onClick={() => setTerminalOpen((value: boolean) => !value)} type="button">
            {terminalOpen ? "Hide Terminal" : "Open Terminal"}
          </button>
        </header>

        <div className="message-feed">
          {messages.map((message: Message, index: number) => (
            <article className={`bubble ${message.role}`} key={`${message.role}-${index}`}>
              <p>{message.content}</p>
              {message.meta ? <span className="meta-tag">{message.meta}</span> : null}
            </article>
          ))}
        </div>

        {terminalOpen ? (
          <form
            className="terminal-strip"
            onSubmit={(event) => {
              event.preventDefault();
              submit(input);
            }}
          >
            <span className="terminal-icon">&gt;_</span>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Fallback terminal"
            />
            <button disabled={isPending || !input.trim()} type="submit">
              {isPending ? "..." : "GO"}
            </button>
          </form>
        ) : null}

        {error ? <p className="error-text">{error}</p> : null}
      </section>
    </main>
  );
}