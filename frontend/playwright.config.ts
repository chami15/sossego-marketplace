import { resolve } from "node:path";

import { defineConfig, devices } from "@playwright/test";

// O e2e sobe a API de verdade num banco só dele (sossego_e2e, recriado a cada
// execução com as migrations reais e anúncios fictícios de db/semente_e2e.py) e o Vite apontando para ela. Nada toca o
// banco principal nem loja nenhuma.
const BANCO = "postgresql://sossego:sossego@127.0.0.1:5434/sossego_e2e";
const PY = ".venv\\Scripts\\python.exe";
// Pasta de dados só do e2e (imagens desenhadas pela semente, sqlite da coleta): nunca a dados/ real.
const DADOS = resolve(".e2e-dados");

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
    { name: "e2e", testMatch: ["onboarding.spec.ts", "busca.spec.ts", "produto.spec.ts"], use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    // Prints de fases anteriores (prints.spec.ts = 6, prints-fase07/08) são registro:
    // rodá-los de novo sobrescreveria o histórico com a tela atual.
    { name: "prints", testMatch: ["prints-fase09.spec.ts"], use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: `${PY} -m db.semente_e2e ${BANCO} && ${PY} -m uvicorn api.app:app --host 127.0.0.1 --port 8010`,
      cwd: "../backend",
      url: "http://127.0.0.1:8010/api/v1/categorias",
      env: { SOSSEGO_DATABASE_URL: BANCO, SOSSEGO_DIR_DADOS: DADOS },
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
