import {BrandLogo} from '../BrandLogo';

export function NavBar() {
  return (
    <nav aria-label="Primary" className="fixed top-4 md:top-6 left-1/2 -translate-x-1/2 z-50 px-2">
      <div className="inline-flex w-[calc(100vw-1rem)] sm:w-auto max-w-[calc(100vw-1rem)] justify-center px-3 sm:px-5 md:px-7 py-3 md:py-2.5 bg-[#050505]/85 backdrop-blur-md border border-white/10 rounded-2xl md:rounded-full text-xs md:text-sm font-medium text-white/80 shadow-2xl">
        <div className="hide-scrollbar flex items-center justify-start sm:justify-center gap-x-2 sm:gap-x-3 md:gap-x-4 text-[11px] sm:text-xs md:text-sm whitespace-nowrap overflow-x-auto">
          <a href="#" className="inline-flex items-center px-2.5 py-1 rounded-full hover:bg-white/10 transition-colors" aria-label="Back to top">
            <BrandLogo className="h-6 sm:h-7 md:h-8 opacity-95" alt="RARE Agent Native Identity Protocol" />
          </a>
          <a href="/whitepaper" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Whitepaper</a>
          <a href="#rip" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">RIP</a>
          <a href="https://rareid.gitbook.io/developer" target="_blank" rel="noreferrer" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Docs</a>
          <a href="/guide" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">Guide</a>
          <a href="/about" className="px-2.5 py-1 rounded-full hover:bg-white/10 hover:text-white transition-colors">About</a>
        </div>
      </div>
    </nav>
  );
}
