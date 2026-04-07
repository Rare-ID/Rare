# Next.js 集成

仓库已内置 Next.js App Router 模板：

```text
packages/platform/ts/rare-platform-kit-ts/starters/nextjs-app-router
```

## 核心文件

- `lib/rare.ts`：Rare 初始化
- `app/api/rare/auth/challenge/route.ts`
- `app/api/rare/auth/complete/route.ts`
- `middleware.ts`：可按 cookie 保护页面

## 登录完成后写入 Cookie

模板会在 `/auth/complete` 成功后写入：

```text
rare_session
```

之后可在中间件或服务端路由中据此判断登录状态。

