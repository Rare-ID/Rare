# AGENTS_EN.md

This file captures the core handoff context for AI agents working on the Rare LandingPage repository.

## 1. Project Snapshot

- Stack: Vite + React + TypeScript
- Local path: `/Volumes/ST7/Projects/Rare/apps/landing`
- Current public domain: `https://www.rareid.cc`

## 2. Route Map

Routing is lightweight and path-based in `src/main.tsx`:

- `/` -> `src/App.tsx` (landing page)
- `/whitepaper` -> `src/pages/WhitepaperPage.tsx`
- `/about` -> `src/pages/AboutPage.tsx`
- `/guide` -> `src/pages/DocsPage.tsx`

## 3. Content File Conventions

- Whitepaper source: `content/whitepaper.md`
  - Rendered by `/whitepaper` via `?raw` import.
- Agent public entry file: `public/skill.md`
  - Public URL after deploy: `https://www.rareid.cc/skill.md`
  - The Agent onboarding copy in `/guide` points directly to this URL.
  - This file references the following supporting materials:
    - `public/flows.md`
    - `public/parameter-explanations.md`
    - `public/runtime-protocol.md`
- Platform integration sources:
  - Overview: `content/platform/README.md`
  - TypeScript: `content/platform/typescript.md`
  - Python: `content/platform/python.md`
  - The `/guide` Platform tab switches between the overview, TypeScript, and Python guides.

## 4. Current IA / Navigation

- Top nav: `Whitepaper / RIP / Docs / Guide / About`
- `Docs` is the external developer docs link: `https://rareid.gitbook.io/developer`
- `Guide` is the internal route: `/guide`
- Footer links: `Whitepaper / Docs / GitHub / Discord / X`

## 5. UI / Styling Notes

- Global styles: `src/index.css`
- Typography accents used in guide/whitepaper pages:
  - `Cormorant Garamond`
  - `Manrope`
- Mobile navbar behavior:
  - forced single-row horizontal scroll
  - utility class: `hide-scrollbar`

## 6. Common Commands

Recommended from the Rare repository root:

- Install: `npm --prefix apps/landing install`
- Dev: `npm --prefix apps/landing run dev`
- Type-check: `npm --prefix apps/landing run lint`
- Build: `npm --prefix apps/landing run build`
- Preview: `npm --prefix apps/landing run preview`

## 7. GitHub Metadata

- LandingPage has been merged into the Rare monorepo:
  - `https://github.com/Rare-ID/Rare`

## 8. Recommended Push Flow

1. `git -C /Volumes/ST7/Projects/Rare status --short`
2. `npm --prefix apps/landing run lint && npm --prefix apps/landing run build`
3. `git add -A && git commit -m "<type>: <message>"`
4. `git push origin main`

## 9. Maintenance Rules

- If Agent onboarding content changes, update `public/skill.md` and any referenced supporting files directly, and keep the CLI-first wording aligned with the main repository `skills/rare-agent/`.
- If whitepaper content changes, edit only `content/whitepaper.md`.
- Do not hand-edit `dist/`; rebuild from source.
