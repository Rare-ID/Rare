import {ArrowRight} from 'lucide-react';
import {BrandLogo} from './components/BrandLogo';
import {NavBar} from './components/layout/NavBar';
import {CodeBlock, LinkButton, Section, SectionTitle} from './components/ui/Section';
import {usePageSeo} from './seo';

export default function App() {
  usePageSeo('/');

  return (
    <div className="min-h-screen font-sans overflow-x-hidden bg-[#050505] text-[#fcfcfc]">
      <NavBar />

      <header className="relative min-h-screen flex flex-col justify-between pt-24 md:pt-8 pb-12 px-6 md:px-8 border-b border-white/10 overflow-hidden">
        <div className="flex justify-between items-start w-full max-w-[1400px] mx-auto z-10">
          <div className="font-mono text-xs md:text-sm uppercase tracking-[0.2em] text-white/50">Protocol v1.0.0</div>
          <div className="font-mono text-xs md:text-sm uppercase tracking-[0.2em] text-white/50 text-right">
            Agent-Native
            <br />
            Identity Layer
          </div>
        </div>

        <div className="flex-1 flex flex-col justify-center w-full max-w-[1400px] mx-auto z-10 mt-12 mb-12">
          <h1
            className="font-black uppercase tracking-tighter leading-[0.8]"
            style={{
              fontSize: 'clamp(8rem, 28vw, 32rem)',
              marginLeft: '-0.04em',
              letterSpacing: '-0.04em',
            }}
          >
            <span className="block text-white mix-blend-difference">RARE</span>
            <span
              className="mt-[-2%] block text-transparent"
              style={{
                WebkitTextStroke: '1px rgba(255,255,255,0.2)',
              }}
            >
              PROTOCOL
            </span>
          </h1>
        </div>

        <div className="w-full max-w-[1400px] mx-auto z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-7">
            <p className="text-2xl md:text-4xl lg:text-5xl font-medium tracking-tight leading-[1.1] mb-6">
              Identity belongs to <span className="italic font-serif text-white/70">agents</span>.
            </p>
            <p className="text-lg md:text-xl text-white/60 max-w-xl leading-relaxed font-light">
              Agents identify with keys, act with signatures,
              <br />
              and carry portable trust across platforms.
            </p>
          </div>

          <div className="lg:col-span-5 flex flex-col sm:flex-row lg:justify-end gap-4">
            <a href="/whitepaper" className="group relative inline-flex items-center justify-center px-8 py-4 bg-white text-black font-medium text-sm uppercase tracking-widest overflow-hidden">
              <span className="relative z-10 flex items-center gap-2">
                Read Whitepaper
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </span>
              <div className="absolute inset-0 bg-[#f2f2f2] transform scale-x-0 origin-left group-hover:scale-x-100 transition-transform duration-300 ease-out"></div>
            </a>
            <a href="/guide#agent-onboarding-guide" className="inline-flex items-center justify-center px-8 py-4 border border-white/20 text-white font-medium text-sm uppercase tracking-widest hover:bg-white/5 transition-colors">
              Join Rare
            </a>
          </div>
        </div>

        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vw] max-w-[1000px] max-h-[1000px] rounded-full border border-white/5 opacity-50 pointer-events-none"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] max-w-[750px] max-h-[750px] rounded-full border border-white/5 opacity-50 pointer-events-none"></div>
      </header>

      <main className="max-w-3xl mx-auto px-6 md:px-8 mt-24">
        <Section id="whitepaper">
          <SectionTitle>The Identity Layer for Agent-Native Products</SectionTitle>

          <div className="prose prose-invert max-w-none mb-12">
            <p className="text-lg leading-relaxed text-white/80">
              Most internet identity is built for humans: emails, passwords, and OAuth accounts. Agents need something else. They identify
              with keys, act with signatures, and need trust and permissions that can travel across products.
            </p>
            <p className="text-lg font-medium mt-6 text-white">
              Rare packages those capabilities into a public protocol, a reference service, an Agent CLI, and platform integration kits.
            </p>
          </div>

          <div className="space-y-8">
            <h3 className="text-sm font-mono uppercase tracking-widest text-white/50">Today's platforms are not built for agents</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <h4 className="font-semibold mb-2 text-white">1. Registration-based identity</h4>
                <p className="text-white/60 text-sm">Agents must create accounts everywhere.</p>
              </div>
              <div>
                <h4 className="font-semibold mb-2 text-white">2. Platform-silo trust</h4>
                <p className="text-white/60 text-sm">Reputation cannot travel.</p>
              </div>
              <div>
                <h4 className="font-semibold mb-2 text-white">3. No standard capability model</h4>
                <p className="text-white/60 text-sm">Each platform invents its own tokens and permissions.</p>
              </div>
              <div>
                <h4 className="font-semibold mb-2 text-white">4. No shared governance signals</h4>
                <p className="text-white/60 text-sm">Abuse on one platform doesn't inform another.</p>
              </div>
            </div>

            <div className="mt-8 p-4 border-l-2 border-white bg-white/5">
              <p className="font-mono text-sm text-white/80">The internet lacks a native identity system for autonomous agents.</p>
            </div>
          </div>
        </Section>

        <Section id="build">
          <SectionTitle>How Rare Works</SectionTitle>

          <div className="space-y-12">
            <div>
              <h3 className="text-xl font-medium mb-4 flex items-center gap-2 text-white">
                <span className="font-mono text-white/40 text-sm">01</span> Agent Identity
              </h3>
              <CodeBlock>
{`agent_id = Ed25519 public key
Signatures prove control`}
              </CodeBlock>
              <p className="mt-4 text-white/70">
                `agent_id` is always the Ed25519 public key. Control is proven with signatures, and platforms authenticate delegated
                session keys rather than relying on bearer identity tokens.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-4 flex items-center gap-2 text-white">
                <span className="font-mono text-white/40 text-sm">02</span> Trust Levels
              </h3>
              <p className="mb-4 text-white/70">
                Rare trust is expressed through attestations such as L0, L1, and L2. Platforms can map those signals to their own
                governance and access rules.
              </p>
              <CodeBlock>
{`L0 — public attestation
L1 — email-backed human verification
L2 — stronger social proof`}
              </CodeBlock>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-4 flex items-center gap-2 text-white">
                <span className="font-mono text-white/40 text-sm">03</span> Capability Sessions
              </h3>
              <p className="mb-4 text-white/70">
                Rare avoids long-lived shared secrets. Agents delegate short-lived session keys, and platforms verify actions against the
                delegated key instead of the long-term identity key.
              </p>
              <ul className="list-disc list-inside text-white/70 space-y-1 ml-2">
                <li>Replay protection is mandatory.</li>
                <li>Fixed signing inputs are protocol requirements.</li>
                <li>Capability sessions stay short-lived and scoped.</li>
              </ul>
            </div>
          </div>
        </Section>

        <Section>
          <SectionTitle>Trust Network</SectionTitle>
          <p className="text-lg text-white/80 mb-6">
            Agents do not belong to one platform.
            <br />
            They carry verifiable identity, trust level, and capability across many.
          </p>
          <div className="mb-8">
            <CodeBlock>
{`              [ Rare Identity Layer ]
             /            |            \\
         Agent       Platform A      Platform B`}
            </CodeBlock>
          </div>
          <p className="text-lg text-white/80">
            Rare is not a destination app.
            <br />
            It is the protocol, reference service, and integration layer behind agent actions.
          </p>
        </Section>

        <Section id="blogs">
          <SectionTitle>Use Cases</SectionTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-10">
            <div>
              <h3 className="font-semibold text-lg mb-2 text-white">Autonomous AI agents</h3>
              <p className="text-white/70">Agents can carry portable identity across products without falling back to account-by-account setup.</p>
            </div>
            <div>
              <h3 className="font-semibold text-lg mb-2 text-white">Agent marketplaces</h3>
              <p className="text-white/70">Trust signaling and history can travel with the agent across the ecosystem.</p>
            </div>
            <div>
              <h3 className="font-semibold text-lg mb-2 text-white">API ecosystems</h3>
              <p className="text-white/70">Platforms can gate capabilities dynamically based on Rare trust levels and attestation policy.</p>
            </div>
            <div>
              <h3 className="font-semibold text-lg mb-2 text-white">Cross-platform governance</h3>
              <p className="text-white/70">Abuse events and policy signals can propagate across different ecosystems.</p>
            </div>
          </div>
        </Section>

        <Section id="rip">
          <SectionTitle>Rare Implementation Proposals (RIP)</SectionTitle>
          <p className="text-white/80 mb-6">
            RIPs govern protocol evolution. The current index lives in the main Rare monorepo and includes accepted RIP-0001 to RIP-0005,
            covering Identity Attestation, Delegation, Challenge/Signing Inputs, Key Rotation, and Platform Onboarding & Events.
          </p>

          <div className="mb-8">
            <p className="text-sm font-mono text-white/50 mb-2 uppercase tracking-widest">Process</p>
            <div className="flex items-center gap-3 font-mono text-sm">
              <span className="bg-white/10 px-2 py-1 text-white/90">Draft</span>
              <span className="text-white/40">↔</span>
              <span className="bg-white/10 px-2 py-1 text-white/90">Review</span>
              <ArrowRight className="w-3 h-3 text-white/40" />
              <span className="bg-white/10 px-2 py-1 text-white/90">Accepted</span>
              <ArrowRight className="w-3 h-3 text-white/40" />
              <span className="bg-white/10 px-2 py-1 text-white/90">Final</span>
            </div>
            <p className="mt-4 text-sm text-white/60">Side states: Withdrawn (from Draft/Review/Accepted), Superseded (from Accepted/Final).</p>
            <p className="mt-2 text-sm text-white/60">
              Promotion to Accepted requires two maintainer approvals and passing RIP CI validation, as defined in RIP-0000.
            </p>
          </div>

          <div className="flex flex-wrap gap-4">
            <LinkButton href="https://github.com/Rare-ID/Rare/tree/main/docs/rip">View RIP Repository</LinkButton>
            <LinkButton href="https://github.com/Rare-ID/Rare/blob/main/docs/rip/CONTRIBUTING_RIP.md">Submit a RIP</LinkButton>
          </div>
        </Section>

        <footer className="py-12 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 border-t border-white/10">
          <div className="space-y-2">
            <BrandLogo className="h-8 md:h-9 opacity-90" alt="RARE Agent Native Identity Protocol" />
            <p className="text-xs font-mono uppercase tracking-[0.15em] text-white/45">Agent Native Identity Protocol</p>
          </div>
          <div className="flex flex-wrap gap-6 text-sm font-medium text-white/60">
            <a href="/whitepaper" className="hover:text-white transition-colors">Whitepaper</a>
            <a href="https://rareid.gitbook.io/developer" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">Docs</a>
            <a href="https://github.com/Rare-ID" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">GitHub</a>
            <a href="https://discord.gg/SNWYHS4nfW" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">Discord</a>
            <a href="https://x.com/rareaip" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">X</a>
          </div>
        </footer>
      </main>
    </div>
  );
}
