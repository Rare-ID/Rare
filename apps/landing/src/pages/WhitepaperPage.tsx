import {ArrowLeft} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {BrandLogo} from '../components/BrandLogo';
import {usePageSeo} from '../seo';
import whitepaperSource from '../../content/whitepaper.md?raw';

const hasWhitepaperContent = whitepaperSource.trim().length > 0;

export default function WhitepaperPage() {
  usePageSeo('/whitepaper');

  return (
    <div className="min-h-screen font-sans overflow-x-hidden bg-[#050505] text-[#fcfcfc]">
      <nav aria-label="Whitepaper" className="fixed top-4 md:top-6 left-1/2 -translate-x-1/2 z-50 px-2">
        <div className="inline-flex w-[calc(100vw-1rem)] sm:w-auto max-w-[calc(100vw-1rem)] justify-center px-3 sm:px-5 md:px-7 py-3 md:py-2.5 bg-[#050505]/85 backdrop-blur-md border border-white/10 rounded-2xl md:rounded-full text-xs md:text-sm font-medium text-white/80 shadow-2xl">
          <div className="hide-scrollbar flex items-center justify-start sm:justify-center gap-x-2 sm:gap-x-3 md:gap-x-4 text-[11px] sm:text-xs md:text-sm whitespace-nowrap overflow-x-auto">
            <a href="/" className="inline-flex items-center px-2.5 py-1 rounded-full hover:bg-white/10 transition-colors" aria-label="Back to home">
              <BrandLogo className="h-6 sm:h-7 md:h-8 opacity-95" alt="RARE Agent Native Identity Protocol" />
            </a>
            <a href="/" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">
              <ArrowLeft className="w-3.5 h-3.5" /> Home
            </a>
            <a href="https://github.com/Rare-ID" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">GitHub</a>
            <a href="https://rareid.gitbook.io/developer" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Docs</a>
            <a href="/guide" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Guide</a>
            <a href="https://x.com/rareaip" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">X</a>
          </div>
        </div>
      </nav>

      <main className="relative max-w-4xl mx-auto px-6 md:px-8 pt-28 md:pt-36 pb-20">
        <div className="absolute top-40 left-1/2 -translate-x-1/2 w-[88vw] h-[88vw] max-w-[840px] max-h-[840px] rounded-full border border-white/5 opacity-40 pointer-events-none"></div>

        <header className="relative z-10 border-b border-white/10 pb-10 mb-10">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/50">Rare • Canonical Document</p>
          <h1 className="mt-4 text-5xl md:text-7xl leading-[0.95] tracking-tight [font-family:var(--font-elevated)] text-white">Whitepaper</h1>
          <p className="mt-5 text-base md:text-lg text-white/65 max-w-2xl [font-family:var(--font-reading)]">
            Formal specification and ecosystem framing for agent-native identity, trust, and delegated capability sessions.
          </p>
        </header>

        {hasWhitepaperContent ? (
          <article className="whitepaper-prose relative z-10">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{whitepaperSource}</ReactMarkdown>
          </article>
        ) : (
          <section className="relative z-10 border border-white/10 rounded-2xl bg-white/5 p-6 md:p-8">
            <h2 className="text-2xl md:text-3xl [font-family:var(--font-elevated)] text-white">Whitepaper Draft Pending</h2>
            <p className="mt-4 text-white/70 [font-family:var(--font-reading)] leading-relaxed">
              The file <code>apps/landing/content/whitepaper.md</code> is currently empty on disk. Save your whitepaper content in that file and this page will render it automatically.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}
