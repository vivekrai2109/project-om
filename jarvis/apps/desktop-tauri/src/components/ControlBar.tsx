import { useState } from "react";

type ControlBarProps = {
  isPending: boolean;
  onSendCommand: (message: string) => void;
};

const STARTER_COMMANDS = [
  "Jarvis how are you operating",
  "Commander show backend status",
  "Omnira explain the active model path",
  "Boss what did you learn today",
];

export function ControlBar({ isPending, onSendCommand }: ControlBarProps) {
  const [input, setInput] = useState("");

  const submit = (message: string) => {
    const normalized = message.trim();
    if (!normalized) {
      return;
    }
    onSendCommand(normalized);
    setInput("");
  };

  return (
    <section className="panel-surface control-panel">
      <div className="panel-heading compact">
        <span className="eyebrow">Command Bar</span>
        <h3>Typed bridge into Python commander</h3>
      </div>
      <form
        className="command-form"
        onSubmit={(event) => {
          event.preventDefault();
          submit(input);
        }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Type a command for JARVIS or OMNIRA"
        />
        <button className="action-button primary" disabled={isPending || !input.trim()} type="submit">
          {isPending ? "Routing..." : "Send"}
        </button>
      </form>
      <div className="starter-row">
        {STARTER_COMMANDS.map((command) => (
          <button key={command} className="starter-chip" onClick={() => submit(command)} type="button">
            {command}
          </button>
        ))}
      </div>
    </section>
  );
}