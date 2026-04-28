import type {ReactNode} from 'react';

type SectionProps = {
  children: ReactNode;
  className?: string;
  id?: string;
};

export function Section({children, className = '', id}: SectionProps) {
  return (
    <section id={id} className={`py-16 md:py-24 border-b border-white/10 last:border-0 ${className}`}>
      {children}
    </section>
  );
}

export function SectionTitle({children}: {children: ReactNode}) {
  return <h2 className="text-2xl md:text-3xl font-semibold tracking-tight mb-8 text-white">{children}</h2>;
}

export function CodeBlock({children}: {children: ReactNode}) {
  return (
    <div className="bg-white/5 p-4 md:p-6 rounded-lg font-mono text-sm overflow-x-auto border border-white/10 text-white/80">
      <pre>
        <code>{children}</code>
      </pre>
    </div>
  );
}

type LinkButtonProps = {
  href: string;
  children: ReactNode;
  primary?: boolean;
};

export function LinkButton({href, children, primary = false}: LinkButtonProps) {
  return (
    <a
      href={href}
      className={`inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium transition-colors ${
        primary ? 'bg-white text-black hover:bg-white/80' : 'border border-white/20 text-white hover:bg-white/5'
      }`}
    >
      {children}
    </a>
  );
}
