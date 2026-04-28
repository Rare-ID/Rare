/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly APP_URL?: string;
}

declare module '*.md?raw' {
  const content: string;
  export default content;
}
