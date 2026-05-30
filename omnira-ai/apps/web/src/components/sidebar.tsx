import Link from "next/link";

const items = [
  { label: "Chat", href: "/chat" },
  { label: "Agents", href: "/chat#agents" },
  { label: "Memory", href: "/chat#memory" },
  { label: "Models", href: "/chat#models" },
  { label: "Lab", href: "/chat#lab" },
  { label: "Bench", href: "/chat#bench" },
  { label: "Actions", href: "/chat#actions" },
  { label: "Settings", href: "/chat#settings" },
];

export function Sidebar() {
  return (
    <aside className="flex w-full flex-col gap-6 rounded-[28px] border border-white/60 bg-white/75 p-5 shadow-panel backdrop-blur xl:w-72">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-[0.28em] text-slate-500">OMNIRA Studio</p>
        <h1 className="text-2xl font-semibold text-ink">Your Personal Intelligence OS</h1>
        <p className="text-sm leading-6 text-slate-600">
          Route every task through the right model, memory, and safety boundary.
        </p>
      </div>

      <nav className="grid gap-2">
        {items.map((item) => (
          <Link
            className="rounded-2xl border border-transparent px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:bg-sky-50 hover:text-ink"
            href={item.href}
            key={item.label}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="rounded-2xl bg-ink px-4 py-4 text-white">
        <p className="text-xs uppercase tracking-[0.24em] text-sky-200">Current Focus</p>
        <p className="mt-2 text-lg font-semibold">OMNIRA Platform 7B v0.1</p>
        <p className="mt-2 text-sm text-slate-300">
          Qwen-derived specialist target for Azure, Terraform, Kubernetes, and CI/CD workflows.
        </p>
      </div>
    </aside>
  );
}
