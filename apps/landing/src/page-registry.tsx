import type {ComponentType} from 'react';
import App from './App';
import AboutPage from './pages/AboutPage';
import DocsPage from './pages/DocsPage';
import WhitepaperPage from './pages/WhitepaperPage';
import {normalizePublicPath, type PublicPath} from './routes';

const GuideHubPage = () => <DocsPage pathname="/guide" />;
const GuidePlatformIndexPage = () => <DocsPage pathname="/guide/platform" />;
const GuidePlatformTypeScriptPage = () => <DocsPage pathname="/guide/platform/typescript" />;
const GuidePlatformPythonPage = () => <DocsPage pathname="/guide/platform/python" />;

export const pageMap: Record<PublicPath, ComponentType> = {
  '/': App,
  '/about': AboutPage,
  '/guide': GuideHubPage,
  '/guide/platform': GuidePlatformIndexPage,
  '/guide/platform/typescript': GuidePlatformTypeScriptPage,
  '/guide/platform/python': GuidePlatformPythonPage,
  '/whitepaper': WhitepaperPage,
};

export function getPageComponent(pathname: string): ComponentType {
  return pageMap[normalizePublicPath(pathname)];
}
