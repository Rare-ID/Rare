import {renderToString} from 'react-dom/server';
import {getPageComponent} from './page-registry';

export function renderPath(pathname: string) {
  const Page = getPageComponent(pathname);
  return renderToString(<Page />);
}
