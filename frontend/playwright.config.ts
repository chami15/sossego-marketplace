import { defineConfig, devices } from "@playwright/test";

// O e2e sobe a API de verdade num banco só dele (sossego_e2e, recriado a cada
// execução com as migrations reais e anúncios fictícios de db/semente_e2e.py) e o Vite apontando para ela. Nada toca o
// banco principal nem loja nenhuma.
const BANCO = "postgresql://sossego:sossego@127.0.0.1:5434/sossego_e2e";
const PY = ".venv\\Scripts\\python.exe";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5180",
    locale: "pt-BR",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "e2e", testMatch: ["onboarding.spec.ts", "busca.spec.ts"], use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "prints", testMatch: ["prints.spec.ts", "prints-fase07.spec.ts"], use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: `${PY} -m db.semente_e2e ${BANCO} && ${PY} -m uvicorn api.app:app --host 127.0.0.1 --port 8010`,
      cwd: "../backend",
      url: "http://127.0.0.1:8010/api/v1/categorias",
      env: { SOSSEGO_DATABASE_URL: BANCO },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npx vite",
      url: "http://127.0.0.1:5180",
      env: { SOSSEGO_API: "http://127.0.0.1:8010", SOSSEGO_WEB_PORTA: "5180" },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
