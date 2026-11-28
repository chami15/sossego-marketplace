import { expect, test, type Page } from "@playwright/test";

// Prints da Fase 8 em docs/prints/fase-08/: home e busca com o card novo e a
// página de produto, com o banco do e2e semeado por backend/db/semente_e2e.py.
const TELAS = [
  { nome: "desktop", viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
  { nome: "mobile", viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 },
];

const cards = (p: Page) => p.locator(".grade-cards .card");

async function idDe(page: Page, q: string) {
  const r = await page.request.get(`/api/v1/busca?q=${encodeURIComponent(q)}`);
  return (await r.json()).resultados[0].id as number;
}

for (const tela of TELAS) {
  test.describe(tela.nome, () => {
    test.use({ viewport: tela.viewport, deviceScaleFactor: tela.deviceScaleFactor, reducedMotion: "reduce" });

    const foto = async (page: Page, n: string, inteira = true) => {
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: `../docs/prints/fase-08/${tela.nome}-${n}.png`, fullPage: inteira });
    };

    test.beforeEach(async ({ page }) => {
      const r = await page.request.post("/api/v1/perfis", {
        data: { faixa_etaria: "25-34", categorias: ["games", "jogos-tabuleiro"], lojas: [], interesses: [] },
      });
      const { id } = await r.json();
      await page.addInitScript((pid) => localStorage.setItem("sossego.perfil", pid), id);
    });

    test("cards", async ({ page }) => {
      await page.goto("/");
      await expect(cards(page).first()).toBeVisible();
      await page.mouse.move(0, 0);
      await foto(page, "01-home");

      await page.goto("/busca?q=ps5");
      await expect(cards(page)).toHaveCount(2);
      await page.mouse.move(0, 0);
      await foto(page, "02-busca");

      await page.goto("/busca?categoria=jogos-tabuleiro");
      await expect(cards(page)).toHaveCount(3);
      if (tela.nome === "desktop") await cards(page).first().hover(); // botão vigiar aparece no hover
      await foto(page, "03-categoria-hover");
    });

    test("produto", async ({ page }) => {
      await page.goto(`/produto/${await idDe(page, "console ps5")}`);
      await expect(page.locator(".melhor")).toBeVisible();
      await expect(page.locator(".calc__veredito")).not.toBeEmpty();
      await page.mouse.move(0, 0);
      await foto(page, "04-produto");

      // Mira do gráfico sobre a coleta mais recente.
      const svg = page.locator(".grafico__area svg");
      await svg.scrollIntoViewIfNeeded();
      const caixa = (await svg.boundingBox())!;
      await page.mouse.move(caixa.x + caixa.width * 0.6, caixa.y + caixa.height / 2);
      await expect(page.locator(".grafico__dica")).toBeVisible();
      await foto(page, "05-produto-grafico-mira", false);

      await page.goto(`/produto/${await idDe(page, "dualsense")}`);
      await page.getByRole("radio", { name: "Preto" }).locator("xpath=..").click();
      await expect(page.locator("table.ofertas tbody tr")).toHaveCount(1);
      await page.mouse.move(0, 0);
      await foto(page, "06-produto-variacao");

      await page.goto(`/produto/${await idDe(page, "cascadia")}`);
      await expect(page.getByText(/Começamos a acompanhar hoje/)).toBeVisible();
      await page.mouse.move(0, 0);
      await foto(page, "07-produto-um-ponto");
    });
  });
}
