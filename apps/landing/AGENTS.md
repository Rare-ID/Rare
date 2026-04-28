# AGENTS.md

本文件记录 Rare LandingPage 项目的关键上下文，供后续 Agent 快速接手。

## 1. 项目概览

- 项目类型: Vite + React + TypeScript 单页站点（按路径做页面分发）
- 本地路径: `/Volumes/ST7/Projects/Rare/apps/landing`
- 线上主域名（当前对外）: `https://www.rareid.cc`

## 2. 关键页面与路由

`src/main.tsx` 使用 `window.location.pathname` 做轻量路由映射:

- `/` -> `src/App.tsx`（主页）
- `/whitepaper` -> `src/pages/WhitepaperPage.tsx`
- `/about` -> `src/pages/AboutPage.tsx`
- `/guide` -> `src/pages/DocsPage.tsx`

## 3. 内容文件约定

- Whitepaper 源文件: `content/whitepaper.md`
  - 白皮书页面通过 `?raw` 直接渲染该文件。
- Agent 对外入口文件: `public/skill.md`
  - 线上地址（部署后）: `https://www.rareid.cc/skill.md`
  - `/guide` 页面中的 Agent 引导文案直接指向这个地址。
  - 该文件内部继续引用以下配套材料:
    - `public/flows.md`
    - `public/parameter-explanations.md`
    - `public/runtime-protocol.md`
- Platform 对接文档源文件:
  - 总览: `content/platform/README.md`
  - TypeScript: `content/platform/typescript.md`
  - Python: `content/platform/python.md`
  - `/guide` 页面中的 Platform Tab 按语言切换渲染总览 / TypeScript / Python 指南。

## 4. 导航与信息架构（当前）

- 主导航: `Whitepaper / RIP / Docs / Guide / About`
- `Docs` 指向外链 `https://rareid.gitbook.io/developer`
- `Guide` 指向站内 `/guide`
- Footer: `Whitepaper / Docs / GitHub / Discord / X`

## 5. 样式与前端约定

- 全局样式: `src/index.css`
- 高级字体（whitepaper/guide 页面使用）:
  - `Cormorant Garamond`
  - `Manrope`
- 移动端 Navbar 已做单行横向滚动适配（`hide-scrollbar`）。

## 6. 常用开发命令

推荐在 Rare 仓库根目录执行:

- 安装依赖: `npm --prefix apps/landing install`
- 本地开发: `npm --prefix apps/landing run dev`
- 类型检查: `npm --prefix apps/landing run lint`
- 生产构建: `npm --prefix apps/landing run build`
- 本地预览: `npm --prefix apps/landing run preview`

## 7. GitHub 信息

- LandingPage 已合并到 Rare 主仓库:
  - `https://github.com/Rare-ID/Rare`

## 8. 推送流程（建议）

1. `git -C /Volumes/ST7/Projects/Rare status --short`
2. `npm --prefix apps/landing run lint && npm --prefix apps/landing run build`
3. `git add -A && git commit -m "<type>: <message>"`
4. `git push origin main`

## 9. 维护提示

- 若更新 Agent 对外引导内容，请直接修改 `public/skill.md` 及其引用的配套文件，并保持 CLI-first 口径与主仓库 `skills/rare-agent/` 一致。
- 若更新白皮书内容，只改 `content/whitepaper.md`，页面会自动使用新内容。
- 避免在 `dist/` 手工改内容；以源码为准重新构建。
