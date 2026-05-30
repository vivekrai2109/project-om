import { ChatClient } from "@/components/chat-client";
import { Sidebar } from "@/components/sidebar";

export default function ChatPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 lg:px-8 xl:flex-row xl:items-start">
      <Sidebar />
      <section className="flex-1 space-y-6">
        <header className="rounded-[28px] border border-white/60 bg-white/75 p-6 shadow-panel backdrop-blur">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">OMNIRA Core + Studio</p>
              <h2 className="mt-2 text-3xl font-semibold text-ink">Chat, route, remember, and act safely</h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-slate-600">
              This MVP surfaces routing decisions, model metadata, and safety signals while keeping the backend
              provider-independent and local-first.
            </p>
          </div>
        </header>
        <ChatClient />
      </section>
    </main>
  );
}
