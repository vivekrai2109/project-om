import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col justify-center gap-10 px-6 py-12 lg:px-10">
      <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
        <section className="space-y-8">
          <div className="inline-flex rounded-full border border-sky-200 bg-white/70 px-4 py-2 text-xs uppercase tracking-[0.34em] text-slate-600 backdrop-blur">
            OMNIRA AI
          </div>
          <div className="space-y-5">
            <h1 className="max-w-4xl text-5xl font-semibold tracking-tight text-ink md:text-7xl">
              Your Personal Intelligence OS
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-600 md:text-xl">
              OMNIRA Studio is the front door to a modular AI platform with chat, memory, RAG, agents,
              tool routing, and a provider-independent path from local Qwen workflows to self-hosted
              OMNIRA models.
            </p>
          </div>
          <div className="flex flex-col gap-4 sm:flex-row">
            <Link
              className="rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5"
              href="/chat"
            >
              Open OMNIRA Studio
            </Link>
            <a
              className="rounded-full border border-slate-300 bg-white/70 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:border-sky-300 hover:text-ink"
              href="https://github.com"
            >
              Monorepo Ready
            </a>
          </div>
        </section>

        <section className="rounded-[36px] border border-white/70 bg-white/80 p-6 shadow-panel backdrop-blur">
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="rounded-[28px] bg-slate-950 p-5 text-white">
              <p className="text-xs uppercase tracking-[0.26em] text-sky-300">Orchestrator</p>
              <p className="mt-2 text-2xl font-semibold">OMNIRA Prime</p>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Classifies intent, retrieves memory, applies safety, and routes to the right model.
              </p>
            </div>
            <div className="rounded-[28px] bg-gradient-to-br from-emerald-100 to-sky-100 p-5">
              <p className="text-xs uppercase tracking-[0.26em] text-slate-500">First Target Model</p>
              <p className="mt-2 text-2xl font-semibold text-ink">OMNIRA Platform 7B v0.1</p>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                Qwen-based specialist path for Azure, Terraform, Kubernetes, CI/CD, and SRE support.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
