import {mkdir, readdir, readFile, rm, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {DEFAULT_SITE_URL, getPublicUrl, publicPaths, renderSeoHead} from '../src/seo';
import {getOutputPath, type PublicPath} from '../src/routes';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const distDir = path.join(projectRoot, 'dist');
const ssrDir = path.join(projectRoot, '.ssr');
const ROOT_MARKUP = '<div id="root"></div>';
const SEO_BLOCK_PATTERN = /<!--seo-head:start-->[\s\S]*?<!--seo-head:end-->/;

async function loadRenderer() {
  const ssrFiles = await readdir(ssrDir);
  const entryFile = ssrFiles.find((file) => /^entry-server\.(m?js|cjs)$/.test(file));

  if (!entryFile) {
    throw new Error('Unable to find SSR entry output in .ssr');
  }

  const ssrModule = (await import(pathToFileURL(path.join(ssrDir, entryFile)).href)) as {
    renderPath: (pathname: string) => string;
  };

  return ssrModule.renderPath;
}

async function writePageHtml(pathname: PublicPath, baseHtml: string, renderPath: (pathname: string) => string, siteUrl: string) {
  const renderedMarkup = renderPath(pathname);
  const htmlWithSeo = baseHtml
    .replace(SEO_BLOCK_PATTERN, `<!--seo-head:start-->\n    ${renderSeoHead(pathname, siteUrl)}\n    <!--seo-head:end-->`)
    .replace(ROOT_MARKUP, `<div id="root">${renderedMarkup}</div>`);

  const outputPath = path.join(distDir, getOutputPath(pathname));
  await mkdir(path.dirname(outputPath), {recursive: true});
  await writeFile(outputPath, htmlWithSeo, 'utf8');
}

async function writeRobots(siteUrl: string) {
  const robotsTxt = `User-agent: *\nAllow: /\nDisallow: /cdn-cgi/\n\nSitemap: ${siteUrl}/sitemap.xml\n`;
  await writeFile(path.join(distDir, 'robots.txt'), robotsTxt, 'utf8');
}

async function writeSitemap(siteUrl: string) {
  const urls = publicPaths
    .map((pathname) => {
      const location = getPublicUrl(pathname, siteUrl);
      return `  <url>\n    <loc>${location}</loc>\n  </url>`;
    })
    .join('\n');

  const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
  const sitemapIndexXml = `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <sitemap>\n    <loc>${siteUrl}/sitemap.xml</loc>\n  </sitemap>\n</sitemapindex>\n`;
  await writeFile(path.join(distDir, 'sitemap.xml'), sitemapXml, 'utf8');
  await writeFile(path.join(distDir, 'sitemap-index.xml'), sitemapIndexXml, 'utf8');
}

async function main() {
  const siteUrl = (process.env.APP_URL || DEFAULT_SITE_URL).replace(/\/+$/, '');
  const baseHtml = await readFile(path.join(distDir, 'index.html'), 'utf8');
  const renderPath = await loadRenderer();

  await Promise.all(publicPaths.map((pathname) => writePageHtml(pathname, baseHtml, renderPath, siteUrl)));
  await Promise.all([writeRobots(siteUrl), writeSitemap(siteUrl)]);
  await rm(ssrDir, {recursive: true, force: true});
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
