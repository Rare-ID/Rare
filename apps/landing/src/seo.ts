import {useEffect} from 'react';
import {normalizePublicPath, publicPaths, type PublicPath} from './routes';

const DEFAULT_SITE_URL = 'https://www.rareid.cc';
const SITE_NAME = 'Rare';
const TWITTER_HANDLE = '@rareaip';
const SAME_AS_LINKS = [
  'https://github.com/Rare-ID',
  'https://x.com/rareaip',
  'https://discord.gg/SNWYHS4nfW',
];

type StructuredData = Record<string, unknown>;

type PageSeo = {
  title: string;
  description: string;
  path: PublicPath;
  ogType: 'website' | 'article';
  ogTitle?: string;
  ogDescription?: string;
  imagePath?: string;
  imageAlt?: string;
  schema: (siteUrl: string) => StructuredData[];
};

function withBaseSchema(siteUrl: string) {
  return {
    '@context': 'https://schema.org',
    publisher: {
      '@type': 'Organization',
      name: SITE_NAME,
      url: siteUrl,
      logo: `${siteUrl}/rare-logo-mark.svg`,
      sameAs: SAME_AS_LINKS,
    },
  };
}

const pageSeoMap: Record<PublicPath, PageSeo> = {
  '/': {
    path: '/',
    title: 'Rare | Agent Identity and Trust for AI Agents',
    description:
      'Rare gives AI agents portable identity, trust attestations, a reference service, an Agent CLI, and platform integration kits.',
    ogType: 'website',
    schema: (siteUrl) => [
      {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        name: SITE_NAME,
        alternateName: ['RareID', 'Rare Identity Protocol'],
        url: siteUrl,
        description:
          'Public protocol and tooling for agent identity, trust, and platform integrations.',
        inLanguage: 'en-US',
      },
      {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: SITE_NAME,
        alternateName: ['RareID', 'Rare Identity Protocol'],
        url: siteUrl,
        logo: `${siteUrl}/rare-logo-mark.svg`,
        description:
          'Open-source organization building agent identity protocol infrastructure, reference services, agent tooling, and platform kits.',
        sameAs: SAME_AS_LINKS,
      },
      {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: [
          {
            '@type': 'Question',
            name: 'What is Rare?',
            acceptedAnswer: {
              '@type': 'Answer',
              text: 'Rare is a public protocol and tooling stack for agent identity, trust attestations, delegated sessions, and platform integrations.',
            },
          },
          {
            '@type': 'Question',
            name: 'Is RareID the same as Rare?',
            acceptedAnswer: {
              '@type': 'Answer',
              text: 'Yes. RareID is a common short name for Rare and the Rare Identity Protocol.',
            },
          },
          {
            '@type': 'Question',
            name: 'What does Rare provide?',
            acceptedAnswer: {
              '@type': 'Answer',
              text: 'Rare provides a protocol, reference service, Agent CLI, and platform integration kits for portable agent identity and verification.',
            },
          },
        ],
      },
    ],
  },
  '/about': {
    path: '/about',
    title: 'About Rare | Agent-Native Open-Source Organization',
    description:
      'Learn about Rare, the open-source effort building a public protocol, reference service, Agent CLI, and platform integration kits for agent-native identity.',
    ogType: 'website',
    schema: (siteUrl) => [
      {
        '@context': 'https://schema.org',
        '@type': 'AboutPage',
        name: 'About Rare',
        url: getPublicUrl('/about', siteUrl),
        description:
          'Background on the Rare organization, its public protocol, and its agent-native identity direction.',
        ...withBaseSchema(siteUrl),
      },
    ],
  },
  '/guide': {
    path: '/guide',
    title: 'Rare Guide | Agent Onboarding and Platform Integration',
    description:
      'Rare guide for agent onboarding through skill.md and for platform integration with current attestation, verification, and delegated session flows.',
    ogType: 'article',
    schema: (siteUrl) => [
      {
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline: 'Rare Guide',
        about: ['Rare', 'RareID', 'Agent identity protocol'],
        url: getPublicUrl('/guide', siteUrl),
        description:
          'Guide for agent onboarding and platform integration on Rare.',
        ...withBaseSchema(siteUrl),
      },
    ],
  },
  '/guide/platform': {
    path: '/guide/platform',
    title: 'Rare Platform Guide | Platform Integration',
    description:
      'Platform integration overview for Rare, including quickstart vs full-mode, the platform skill entrypoint, and TypeScript and Python guides.',
    ogType: 'article',
    schema: (siteUrl) => [
      {
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline: 'Rare Platform Integration Overview',
        about: ['Rare', 'Rare platform integration', 'Agent identity protocol'],
        url: getPublicUrl('/guide/platform', siteUrl),
        description:
          'Platform integration overview for third-party platforms using Rare, with a platform skill entrypoint and language-specific guides.',
        ...withBaseSchema(siteUrl),
      },
    ],
  },
  '/guide/platform/typescript': {
    path: '/guide/platform/typescript',
    title: 'Rare Platform Guide | TypeScript Integration',
    description:
      'TypeScript quickstart for Rare platform login, auth routes, session handling, and public-only to full-mode upgrade guidance.',
    ogType: 'article',
    schema: (siteUrl) => [
      {
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline: 'Rare Platform Integration for TypeScript',
        about: ['Rare', 'TypeScript', 'Platform SDK'],
        url: getPublicUrl('/guide/platform/typescript', siteUrl),
        description:
          'TypeScript quickstart contract for third-party platforms integrating Rare.',
        ...withBaseSchema(siteUrl),
      },
    ],
  },
  '/guide/platform/python': {
    path: '/guide/platform/python',
    title: 'Rare Platform Guide | Python Integration',
    description:
      'Python quickstart for Rare platform login, FastAPI auth routes, session handling, and public-only to full-mode upgrade guidance.',
    ogType: 'article',
    schema: (siteUrl) => [
      {
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline: 'Rare Platform Integration for Python',
        about: ['Rare', 'Python', 'Platform SDK'],
        url: getPublicUrl('/guide/platform/python', siteUrl),
        description:
          'Python quickstart contract for third-party platforms integrating Rare.',
        ...withBaseSchema(siteUrl),
      },
    ],
  },
  '/whitepaper': {
    path: '/whitepaper',
    title: 'Rare Whitepaper | Rare Identity Protocol Canonical Document',
    description:
      'Read the Rare whitepaper, the canonical Rare Identity Protocol document covering agent identity, trust levels, attestations, and capability sessions.',
    ogType: 'article',
    schema: (siteUrl) => [
      {
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline: 'Rare Whitepaper',
        url: getPublicUrl('/whitepaper', siteUrl),
        description:
          'Canonical whitepaper for Rare and the Rare Identity Protocol specifications.',
        ...withBaseSchema(siteUrl),
      },
    ],
  },
};

type ResolvedSeo = PageSeo & {
  canonicalUrl: string;
  imageUrl: string;
  ogTitle: string;
  ogDescription: string;
};

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function serializeJsonLd(data: StructuredData): string {
  return JSON.stringify(data).replace(/</g, '\\u003c');
}

export function normalizeSiteUrl(siteUrl = DEFAULT_SITE_URL): string {
  return siteUrl.replace(/\/+$/, '') || DEFAULT_SITE_URL;
}

export function getPublicUrl(pathname: string, siteUrl = DEFAULT_SITE_URL): string {
  const canonicalBase = normalizeSiteUrl(siteUrl);
  const path = normalizePublicPath(pathname);
  return path === '/' ? canonicalBase : `${canonicalBase}${path}/`;
}

export function getSiteUrlFromEnvironment(): string {
  const envAppUrl = typeof import.meta !== 'undefined' ? import.meta.env.APP_URL : undefined;
  return normalizeSiteUrl(envAppUrl || DEFAULT_SITE_URL);
}

export function getPageSeo(pathname: string, siteUrl = DEFAULT_SITE_URL): ResolvedSeo {
  const path = normalizePublicPath(pathname);
  const pageSeo = pageSeoMap[path];
  const canonicalBase = normalizeSiteUrl(siteUrl);
  const canonicalUrl = getPublicUrl(path, canonicalBase);
  const imageUrl = `${canonicalBase}${pageSeo.imagePath || '/og-image.png'}`;

  return {
    ...pageSeo,
    canonicalUrl,
    imageUrl,
    ogTitle: pageSeo.ogTitle || pageSeo.title,
    ogDescription: pageSeo.ogDescription || pageSeo.description,
  };
}

export function renderSeoHead(pathname: string, siteUrl = DEFAULT_SITE_URL): string {
  const seo = getPageSeo(pathname, siteUrl);
  const schemaTags = seo.schema(normalizeSiteUrl(siteUrl)).map(
    (entry) =>
      `<script type="application/ld+json" data-rare-seo-managed="true">${serializeJsonLd(entry)}</script>`,
  );

  return [
    `<title>${escapeHtml(seo.title)}</title>`,
    `<meta name="description" content="${escapeHtml(seo.description)}" data-rare-seo-managed="true" />`,
    '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" data-rare-seo-managed="true" />',
    `<link rel="canonical" href="${escapeHtml(seo.canonicalUrl)}" data-rare-seo-managed="true" />`,
    `<meta property="og:type" content="${escapeHtml(seo.ogType)}" data-rare-seo-managed="true" />`,
    `<meta property="og:title" content="${escapeHtml(seo.ogTitle)}" data-rare-seo-managed="true" />`,
    `<meta property="og:description" content="${escapeHtml(seo.ogDescription)}" data-rare-seo-managed="true" />`,
    `<meta property="og:url" content="${escapeHtml(seo.canonicalUrl)}" data-rare-seo-managed="true" />`,
    `<meta property="og:image" content="${escapeHtml(seo.imageUrl)}" data-rare-seo-managed="true" />`,
    '<meta property="og:image:alt" content="Rare brand image" data-rare-seo-managed="true" />',
    `<meta property="og:site_name" content="${escapeHtml(SITE_NAME)}" data-rare-seo-managed="true" />`,
    '<meta property="og:locale" content="en_US" data-rare-seo-managed="true" />',
    '<meta name="twitter:card" content="summary_large_image" data-rare-seo-managed="true" />',
    `<meta name="twitter:title" content="${escapeHtml(seo.ogTitle)}" data-rare-seo-managed="true" />`,
    `<meta name="twitter:description" content="${escapeHtml(seo.ogDescription)}" data-rare-seo-managed="true" />`,
    `<meta name="twitter:image" content="${escapeHtml(seo.imageUrl)}" data-rare-seo-managed="true" />`,
    '<meta name="twitter:image:alt" content="Rare brand image" data-rare-seo-managed="true" />',
    `<meta name="twitter:site" content="${escapeHtml(TWITTER_HANDLE)}" data-rare-seo-managed="true" />`,
    `<meta name="author" content="${escapeHtml(SITE_NAME)}" data-rare-seo-managed="true" />`,
    ...schemaTags,
  ].join('\n    ');
}

function appendManagedMeta(
  doc: Document,
  tagName: 'meta' | 'link' | 'script',
  attributes: Record<string, string>,
  textContent?: string,
) {
  const element = doc.createElement(tagName);
  element.setAttribute('data-rare-seo-managed', 'true');

  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }

  if (textContent) {
    element.textContent = textContent;
  }

  doc.head.appendChild(element);
}

export function applyDocumentSeo(pathname: string, siteUrl = getSiteUrlFromEnvironment()) {
  if (typeof document === 'undefined') {
    return;
  }

  const seo = getPageSeo(pathname, siteUrl);
  document.title = seo.title;

  document.head.querySelectorAll('[data-rare-seo-managed="true"]').forEach((node) => node.remove());

  appendManagedMeta(document, 'meta', {name: 'description', content: seo.description});
  appendManagedMeta(document, 'meta', {
    name: 'robots',
    content: 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1',
  });
  appendManagedMeta(document, 'link', {rel: 'canonical', href: seo.canonicalUrl});
  appendManagedMeta(document, 'meta', {property: 'og:type', content: seo.ogType});
  appendManagedMeta(document, 'meta', {property: 'og:title', content: seo.ogTitle});
  appendManagedMeta(document, 'meta', {property: 'og:description', content: seo.ogDescription});
  appendManagedMeta(document, 'meta', {property: 'og:url', content: seo.canonicalUrl});
  appendManagedMeta(document, 'meta', {property: 'og:image', content: seo.imageUrl});
  appendManagedMeta(document, 'meta', {property: 'og:image:alt', content: 'Rare brand image'});
  appendManagedMeta(document, 'meta', {property: 'og:site_name', content: SITE_NAME});
  appendManagedMeta(document, 'meta', {property: 'og:locale', content: 'en_US'});
  appendManagedMeta(document, 'meta', {name: 'twitter:card', content: 'summary_large_image'});
  appendManagedMeta(document, 'meta', {name: 'twitter:title', content: seo.ogTitle});
  appendManagedMeta(document, 'meta', {name: 'twitter:description', content: seo.ogDescription});
  appendManagedMeta(document, 'meta', {name: 'twitter:image', content: seo.imageUrl});
  appendManagedMeta(document, 'meta', {name: 'twitter:image:alt', content: 'Rare brand image'});
  appendManagedMeta(document, 'meta', {name: 'twitter:site', content: TWITTER_HANDLE});
  appendManagedMeta(document, 'meta', {name: 'author', content: SITE_NAME});

  for (const entry of seo.schema(normalizeSiteUrl(siteUrl))) {
    appendManagedMeta(document, 'script', {type: 'application/ld+json'}, serializeJsonLd(entry));
  }
}

export function usePageSeo(pathname: PublicPath) {
  useEffect(() => {
    applyDocumentSeo(pathname);
  }, [pathname]);
}

export {DEFAULT_SITE_URL, SITE_NAME, SAME_AS_LINKS, publicPaths};
