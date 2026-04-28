import {ArrowLeft} from 'lucide-react';
import {BrandLogo} from '../components/BrandLogo';
import {usePageSeo} from '../seo';

export default function AboutPage() {
  usePageSeo('/about');

  return (
    <div className="min-h-screen font-sans overflow-x-hidden bg-[#050505] text-[#fcfcfc]">
      <nav aria-label="About" className="fixed top-4 md:top-6 left-1/2 -translate-x-1/2 z-50 px-2">
        <div className="inline-flex w-[calc(100vw-1rem)] sm:w-auto max-w-[calc(100vw-1rem)] justify-center px-3 sm:px-5 md:px-7 py-3 md:py-2.5 bg-[#050505]/85 backdrop-blur-md border border-white/10 rounded-2xl md:rounded-full text-xs md:text-sm font-medium text-white/80 shadow-2xl">
          <div className="hide-scrollbar flex items-center justify-start sm:justify-center gap-x-2 sm:gap-x-3 md:gap-x-4 text-[11px] sm:text-xs md:text-sm whitespace-nowrap overflow-x-auto">
            <a href="/" className="inline-flex items-center px-2.5 py-1 rounded-full hover:bg-white/10 transition-colors" aria-label="Back to home">
              <BrandLogo className="h-6 sm:h-7 md:h-8 opacity-95" alt="RARE Agent Native Identity Protocol" />
            </a>
            <a href="/" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">
              <ArrowLeft className="w-3.5 h-3.5" /> Home
            </a>
            <a href="/whitepaper" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Whitepaper</a>
            <a href="https://github.com/Rare-ID" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">GitHub</a>
            <a href="https://x.com/rareaip" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">X</a>
          </div>
        </div>
      </nav>

      <main className="relative max-w-4xl mx-auto px-6 md:px-8 pt-28 md:pt-36 pb-20">
        <div className="absolute top-36 left-1/2 -translate-x-1/2 w-[88vw] h-[88vw] max-w-[840px] max-h-[840px] rounded-full border border-white/5 opacity-40 pointer-events-none"></div>

        <section className="relative z-10 border border-white/10 bg-white/5 rounded-2xl p-7 md:p-10">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/50">About Rare</p>
          <h1 className="mt-4 text-5xl md:text-7xl leading-[0.95] tracking-tight [font-family:var(--font-elevated)] text-white">Agent-Native Organization</h1>

          <p className="mt-8 text-lg md:text-xl text-white/80 [font-family:var(--font-reading)] leading-relaxed">
            Rare is an open-source effort building a public protocol, reference service, Agent CLI, and platform integration kits for
            agent-native identity.
          </p>
          <p className="mt-4 text-base md:text-lg text-white/70 [font-family:var(--font-reading)] leading-relaxed">
            The project focuses on portable agent identity, trust attestations, delegated sessions, and platform-facing verification flows.
            Governance is intended to move gradually from human-led coordination toward agent participation over time.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <span className="px-3 py-1 bg-white/10 text-sm font-mono text-white/90">Open Source</span>
            <span className="px-3 py-1 bg-white/10 text-sm font-mono text-white/90">Agent-Native</span>
            <span className="px-3 py-1 bg-white/10 text-sm font-mono text-white/90">Human → Agent Governance</span>
          </div>

          <div className="mt-8 flex flex-wrap gap-4 text-sm">
            <a href="https://github.com/Rare-ID" target="_blank" rel="noreferrer" className="px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors">GitHub</a>
            <a href="https://discord.gg/SNWYHS4nfW" target="_blank" rel="noreferrer" className="px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors">Discord</a>
            <a href="https://x.com/rareaip" target="_blank" rel="noreferrer" className="px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors">X</a>
            <a href="mailto:contact@rareid.cc" className="px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors">contact@rareid.cc</a>
          </div>
        </section>
      </main>
    </div>
  );
}
