import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

async function readStarter(relativePath: string): Promise<string> {
  return readFile(
    resolve(process.cwd(), "../../starters", relativePath),
    "utf8",
  );
}

describe("starter templates", () => {
  it("ships a Next.js starter wired to from-env helpers", async () => {
    const libRare = await readStarter("nextjs-app-router/lib/rare.ts");
    const completeRoute = await readStarter(
      "nextjs-app-router/app/api/rare/auth/complete/route.ts",
    );

    expect(libRare).toContain("createRarePlatformKitFromEnv");
    expect(libRare).toContain("createRareSessionResolver");
    expect(completeRoute).toContain("response.cookies.set");
    expect(completeRoute).toContain("result.session_token");
  });

  it("ships an Express starter wired to router and middleware helpers", async () => {
    const server = await readStarter("express/src/server.ts");

    expect(server).toContain("createExpressRareRouter");
    expect(server).toContain("createRareSessionMiddleware");
    expect(server).toContain("createRareActionMiddleware");
  });
});
