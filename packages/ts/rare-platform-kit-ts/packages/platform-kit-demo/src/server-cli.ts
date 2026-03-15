import { readDemoEnv } from "./config";
import { startDemoPlatformServer } from "./server";

async function main(): Promise<void> {
  const env = readDemoEnv();
  const runtime = await startDemoPlatformServer({
    aud: env.platformAud,
    host: env.host,
    port: env.port,
    rareBaseUrl: env.rareBaseUrl,
    rareSignerPublicKeyB64: env.rareSignerPublicKeyB64 || undefined,
  });
  console.log(
    `rare platform demo listening on ${runtime.getUrl()} for aud ${env.platformAud}`,
  );
}

main().catch((error) => {
  const detail = error instanceof Error ? error.message : String(error);
  console.error(detail);
  process.exitCode = 1;
});
