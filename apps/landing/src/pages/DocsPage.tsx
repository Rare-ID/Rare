import {ArrowLeft, Check, Copy} from 'lucide-react';
import {useEffect, useRef, useState} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {BrandLogo} from '../components/BrandLogo';
import {usePageSeo} from '../seo';
import type {PublicPath} from '../routes';
import platformDocIndex from '../../content/platform/README.md?raw';
import platformDocTs from '../../content/platform/typescript.md?raw';
import platformDocPython from '../../content/platform/python.md?raw';

type DocsView = 'agent' | 'platform';
type PlatformDocView = 'index' | 'ts' | 'python';
type DocsPagePath = Extract<
  PublicPath,
  '/guide' | '/guide/platform' | '/guide/platform/typescript' | '/guide/platform/python'
>;
type DocsPageProps = {
  pathname?: DocsPagePath;
};

const agentPrompt = `Read https://www.rareid.cc/skill.md and follow the instructions to register Rare.`;
const platformPrompt = `Read https://www.rareid.cc/rare-platform-integration.md. Follow that Rare platform integration skill to detect the app framework, explain the public-only and full-mode options, ask me to choose, and then integrate Rare login into this Next.js, Express, or FastAPI app.`;

export default function DocsPage({pathname = '/guide'}: DocsPageProps) {
  const [copiedPrompt, setCopiedPrompt] = useState<'agent' | 'platform' | null>(null);
  const agentPromptRef = useRef<HTMLTextAreaElement | null>(null);
  const platformPromptRef = useRef<HTMLTextAreaElement | null>(null);
  const view: DocsView = pathname === '/guide' ? 'agent' : 'platform';
  const platformDocView: PlatformDocView =
    pathname === '/guide/platform/python' ? 'python' : pathname === '/guide/platform/typescript' ? 'ts' : 'index';

  usePageSeo(pathname);

  useEffect(() => {
    const resizePrompt = (element: HTMLTextAreaElement | null) => {
      if (!element) return;
      element.style.height = '0px';
      element.style.height = `${element.scrollHeight}px`;
    };

    const resizePrompts = () => {
      resizePrompt(agentPromptRef.current);
      resizePrompt(platformPromptRef.current);
    };

    resizePrompts();
    window.addEventListener('resize', resizePrompts);
    return () => window.removeEventListener('resize', resizePrompts);
  }, []);

  const handleCopy = async (kind: 'agent' | 'platform', value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedPrompt(kind);
      window.setTimeout(() => setCopiedPrompt((current) => (current === kind ? null : current)), 1800);
    } catch {
      setCopiedPrompt(null);
    }
  };

  const activePlatformDoc =
    platformDocView === 'ts' ? platformDocTs : platformDocView === 'python' ? platformDocPython : platformDocIndex;

  return (
    <div className="min-h-screen font-sans overflow-x-hidden bg-[#050505] text-[#fcfcfc]">
      <nav aria-label="Guide" className="fixed top-4 md:top-6 left-1/2 -translate-x-1/2 z-50 px-2">
        <div className="inline-flex w-[calc(100vw-1rem)] sm:w-auto max-w-[calc(100vw-1rem)] justify-center px-3 sm:px-5 md:px-7 py-3 md:py-2.5 bg-[#050505]/85 backdrop-blur-md border border-white/10 rounded-2xl md:rounded-full text-xs md:text-sm font-medium text-white/80 shadow-2xl">
          <div className="hide-scrollbar flex items-center justify-start sm:justify-center gap-x-2 sm:gap-x-3 md:gap-x-4 text-[11px] sm:text-xs md:text-sm whitespace-nowrap overflow-x-auto">
            <a href="/" className="inline-flex items-center px-2.5 py-1 rounded-full hover:bg-white/10 transition-colors" aria-label="Back to home">
              <BrandLogo className="h-6 sm:h-7 md:h-8 opacity-95" alt="RARE Agent Native Identity Protocol" />
            </a>
            <a href="/" className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">
              <ArrowLeft className="w-3.5 h-3.5" /> Home
            </a>
            <a href="/whitepaper" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Whitepaper</a>
            <a href="/about" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">About</a>
            <a href="https://rareid.gitbook.io/developer" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Docs</a>
            <a href="https://github.com/Rare-ID" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">GitHub</a>
          </div>
        </div>
      </nav>

      <main className="relative max-w-5xl mx-auto px-6 md:px-8 pt-28 md:pt-36 pb-20">
        <div className="absolute top-36 left-1/2 -translate-x-1/2 w-[88vw] h-[88vw] max-w-[920px] max-h-[920px] rounded-full border border-white/5 opacity-40 pointer-events-none"></div>

        <section className="relative z-10 border border-white/10 bg-white/5 rounded-2xl p-7 md:p-10">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/50">Rare Guide</p>
          <h1 className="mt-4 text-4xl md:text-6xl leading-[0.95] tracking-tight [font-family:var(--font-elevated)] text-white">Start from the right path</h1>
          <p className="mt-5 text-base md:text-lg text-white/70 [font-family:var(--font-reading)]">
            Use <span className="text-white">Guide</span> for the fastest Rare setup path. Open <span className="text-white">Docs</span> when you need the full developer reference.
          </p>

          <div className="mt-6 flex flex-wrap gap-3 text-sm">
            <a
              href="https://rareid.gitbook.io/developer"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors"
            >
              Open Developer Docs
            </a>
          </div>

          <div className="mt-8 inline-flex border border-white/15 rounded-full p-1 bg-[#050505]/70">
            <a
              href="/guide"
              className={`px-4 py-2 text-sm rounded-full transition-colors ${view === 'agent' ? 'bg-white text-black' : 'text-white/70 hover:text-white'}`}
            >
              Agent
            </a>
            <a
              href="/guide/platform"
              className={`px-4 py-2 text-sm rounded-full transition-colors ${view === 'platform' ? 'bg-white text-black' : 'text-white/70 hover:text-white'}`}
            >
              Platform
            </a>
          </div>
        </section>

        {view === 'agent' ? (
          <section
            id="agent-onboarding-guide"
            className="relative z-10 mt-8 border border-white/10 bg-white/5 rounded-2xl p-6 md:p-8 scroll-mt-28"
          >
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/50">Agent Path</p>
            <h2 className="mt-3 text-2xl md:text-3xl [font-family:var(--font-elevated)] text-white">Join Rare with your agent</h2>
            <p className="mt-4 max-w-3xl text-white/75 [font-family:var(--font-reading)] leading-relaxed">
              Start with <a href="https://www.rareid.cc/skill.md" target="_blank" rel="noreferrer" className="underline underline-offset-4 decoration-white/40 hover:decoration-white">skill.md</a>.
              It is the single public entrypoint for agent onboarding.
            </p>
            <p className="mt-3 text-white/70 [font-family:var(--font-reading)] leading-relaxed">
              If you want the shortest path, copy the prompt below into your coding agent and let it walk through registration.
            </p>

            <div className="mt-6">
              <textarea
                ref={agentPromptRef}
                readOnly
                rows={1}
                value={agentPrompt}
                className="w-full resize-none overflow-hidden rounded-xl border border-white/15 bg-[#050505]/80 p-4 text-sm text-white/85 font-mono leading-relaxed"
              />
              <button
                onClick={() => handleCopy('agent', agentPrompt)}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors text-sm"
              >
                {copiedPrompt === 'agent' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copiedPrompt === 'agent' ? 'Copied' : 'Copy This Prompt'}
              </button>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-3">
              <div className="border border-white/10 rounded-xl bg-[#050505]/45 p-5">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/45">Step 1</p>
                <p className="mt-3 text-white font-medium">Open the onboarding skill</p>
                <p className="mt-2 text-sm text-white/70 [font-family:var(--font-reading)] leading-relaxed">
                  Use `skill.md` as the canonical Rare onboarding source.
                </p>
              </div>
              <div className="border border-white/10 rounded-xl bg-[#050505]/45 p-5">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/45">Step 2</p>
                <p className="mt-3 text-white font-medium">Register and verify</p>
                <p className="mt-2 text-sm text-white/70 [font-family:var(--font-reading)] leading-relaxed">
                  Create the identity, apply for the needed trust level, and finish login.
                </p>
              </div>
              <div className="border border-white/10 rounded-xl bg-[#050505]/45 p-5">
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/45">Step 3</p>
                <p className="mt-3 text-white font-medium">Use delegated sessions</p>
                <p className="mt-2 text-sm text-white/70 [font-family:var(--font-reading)] leading-relaxed">
                  Sign actions with short-lived scoped session keys after authentication.
                </p>
              </div>
            </div>

            <div className="mt-6">
              <p className="text-white text-lg [font-family:var(--font-elevated)]">Choose how signing keys are managed</p>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border border-white/10 rounded-xl bg-[#050505]/45 p-5">
                  <p className="text-white font-medium">Rare-hosted signer</p>
                  <p className="mt-2 text-white/70 text-sm [font-family:var(--font-reading)] leading-relaxed">
                    Best for the shortest setup. Rare signs behind the API, so your agent does not need local key storage.
                  </p>
                  <p className="mt-3 text-white/60 text-xs uppercase tracking-widest font-mono">Tradeoff: simpler setup, less direct control</p>
                </div>
                <div className="border border-white/10 rounded-xl bg-[#050505]/45 p-5">
                  <p className="text-white font-medium">Self-hosted signer</p>
                  <p className="mt-2 text-white/70 text-sm [font-family:var(--font-reading)] leading-relaxed">
                    Best when you want direct control of signing keys. Your agent stores the key locally and can run its own signer endpoint.
                  </p>
                  <p className="mt-3 text-white/60 text-xs uppercase tracking-widest font-mono">Tradeoff: more setup and key management</p>
                </div>
              </div>
            </div>
          </section>
        ) : (
          <section className="relative z-10 mt-8 border border-white/10 bg-white/5 rounded-2xl p-6 md:p-8">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/50">Platform Path</p>
            <h2 className="text-2xl md:text-3xl [font-family:var(--font-elevated)] text-white mt-3">Platform integration guide</h2>
            <p className="mt-4 max-w-3xl text-white/70 [font-family:var(--font-reading)] leading-relaxed">
              Start with <span className="text-white">public-only / quickstart</span> for Rare login, local verification, and session handling.
              Move to <span className="text-white">full-mode / production</span> only when you need platform registration, durable stores,
              full attestation, or negative event ingest.
            </p>

            {platformDocView === 'index' ? (
              <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                <div className="border border-white/10 rounded-xl bg-[#050505]/45 p-5 md:p-6">
                  <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/50">For Agents</p>
                  <h3 className="mt-3 text-xl text-white [font-family:var(--font-elevated)]">Use the platform integration skill</h3>
                  <p className="mt-3 text-sm text-white/70 [font-family:var(--font-reading)] leading-relaxed">
                    If an agent or coding assistant is wiring Rare into your app, start here. The public skill URL gives the agent the maintained
                    instructions for Next.js App Router, Express, and FastAPI and compares quickstart vs full-mode before editing.
                  </p>
                  <div className="mt-5">
                    <textarea
                      ref={platformPromptRef}
                      readOnly
                      rows={1}
                      value={platformPrompt}
                      className="w-full resize-none overflow-hidden rounded-xl border border-white/15 bg-[#050505]/80 p-4 text-sm text-white/85 font-mono leading-relaxed"
                    />
                    <button
                      onClick={() => handleCopy('platform', platformPrompt)}
                      className="mt-4 inline-flex items-center gap-2 px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors text-sm"
                    >
                      {copiedPrompt === 'platform' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      {copiedPrompt === 'platform' ? 'Copied' : 'Copy Platform Prompt'}
                    </button>
                  </div>
                </div>

                <div className="border border-white/10 rounded-xl bg-[#050505]/45 p-5 md:p-6">
                  <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/50">Manual Path</p>
                  <h3 className="mt-3 text-xl text-white [font-family:var(--font-elevated)]">Choose your stack</h3>
                  <p className="mt-3 text-sm text-white/70 [font-family:var(--font-reading)] leading-relaxed">
                    If you are integrating by hand, use the language quickstart first and extend to full-mode only if production needs it.
                  </p>
                  <div className="mt-5 flex flex-wrap gap-3 text-sm">
                    <a href="/guide/platform/typescript" className="inline-flex items-center justify-center px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors">
                      TypeScript Guide
                    </a>
                    <a href="/guide/platform/python" className="inline-flex items-center justify-center px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors">
                      Python Guide
                    </a>
                    <a
                      href="https://rareid.gitbook.io/developer"
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center justify-center px-4 py-2 border border-white/20 text-white/85 hover:text-white hover:bg-white/5 transition-colors"
                    >
                      Developer Docs
                    </a>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="mt-6 inline-flex border border-white/15 rounded-full p-1 bg-[#050505]/70">
              <a
                href="/guide/platform"
                className={`px-4 py-2 text-sm rounded-full transition-colors ${platformDocView === 'index' ? 'bg-white text-black' : 'text-white/70 hover:text-white'}`}
              >
                Overview
              </a>
              <a
                href="/guide/platform/typescript"
                className={`px-4 py-2 text-sm rounded-full transition-colors ${platformDocView === 'ts' ? 'bg-white text-black' : 'text-white/70 hover:text-white'}`}
              >
                TypeScript
              </a>
              <a
                href="/guide/platform/python"
                className={`px-4 py-2 text-sm rounded-full transition-colors ${platformDocView === 'python' ? 'bg-white text-black' : 'text-white/70 hover:text-white'}`}
              >
                Python
              </a>
            </div>
            <article className="whitepaper-prose mt-6">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{activePlatformDoc}</ReactMarkdown>
            </article>
          </section>
        )}
      </main>
    </div>
  );
}
