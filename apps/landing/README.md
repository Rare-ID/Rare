# Rare Protocol Landing Page

A Vite + React landing page for Rare Protocol.

## Project structure

```text
apps/landing/
├─ public/         # favicon, social preview image, static assets
├─ content/        # whitepaper and guide markdown rendered by React
├─ src/
│  ├─ assets/      # brand assets used by React
│  ├─ components/  # reusable UI and layout components
│  ├─ App.tsx      # page composition
│  ├─ index.css    # global styles + Tailwind imports
│  └─ main.tsx     # React entry
├─ index.html      # SEO metadata + app mount
└─ vite.config.ts  # build/dev config
```

## Run locally

From the Rare repository root:

1. Install dependencies:
   `npm --prefix apps/landing install`
2. Start development server:
   `npm --prefix apps/landing run dev`
3. Run type checks:
   `npm --prefix apps/landing run lint`
4. Build for production:
   `npm --prefix apps/landing run build`
5. Preview production build:
   `npm --prefix apps/landing run preview`
