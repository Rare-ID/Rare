import { readDemoEnv } from "./config";
import { completeDemoRegister } from "./register";

async function main(): Promise<void> {
  const env = readDemoEnv(process.env, { requireDomain: true });
  const response = await completeDemoRegister(env);
  console.log(JSON.stringify(response, null, 2));
}

main().catch((error) => {
  const detail = error instanceof Error ? error.message : String(error);
  console.error(detail);
  process.exitCode = 1;
});
