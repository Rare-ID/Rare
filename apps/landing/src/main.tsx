import {StrictMode} from 'react';
import {createRoot, hydrateRoot} from 'react-dom/client';
import {getPageComponent} from './page-registry';
import {normalizePublicPath} from './routes';
import './index.css';

const currentPath = normalizePublicPath(window.location.pathname);
const ActivePage = getPageComponent(currentPath);
const rootElement = document.getElementById('root')!;
const app = (
  <StrictMode>
    <ActivePage />
  </StrictMode>
);

if (rootElement.hasChildNodes()) {
  hydrateRoot(rootElement, app);
} else {
  createRoot(rootElement).render(app);
}
