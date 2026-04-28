export const publicPaths = [
  '/',
  '/about',
  '/guide',
  '/guide/platform',
  '/guide/platform/typescript',
  '/guide/platform/python',
  '/whitepaper',
] as const;

export type PublicPath = (typeof publicPaths)[number];

export function normalizePublicPath(pathname: string): PublicPath {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  return publicPaths.includes(normalizedPath as PublicPath) ? (normalizedPath as PublicPath) : '/';
}

export function getOutputPath(pathname: PublicPath): string {
  return pathname === '/' ? 'index.html' : `${pathname.slice(1)}/index.html`;
}
