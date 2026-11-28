import { expect, test, type Page } from "@playwright/test";

// Prints da Fase 7 (home, busca, produto provisório) em docs/prints/fase-07/,
// com o banco do e2e semeado por backend/db/semente_e2e.py. Registro histórico:
// fora do projeto "prints" desde a Fase 8 (o produto provisório não existe mais).
const TELAS = [
  { nome: "desktop", viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
  { nome: "mobile", viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 },
];

const cards = (p: Page) => p.locator(".grade-cards .card");

for (const tela of TELAS) {
  test.describe(tela.nome, () => {
    test.use({ viewport: tela.viewport, deviceScaleFactor: tela.deviceScaleFactor, reducedMotion: "reduce" });

    const foto = async (page: Page, n: string) => {
      await page.evaluate(() => document.fonts.ready);
      await page.mouse.move(0, 0);
      await page.screenshot({ path: `../docs/prints/fase-07/${tela.nome}-${n}.png`, fullPage: true });
    };

    test.beforeEach(async ({ page }) => {
      const r = await page.request.post("/api/v1/perfis", {
        data: { faixa_etaria: "25-34", categorias: ["games"], lojas: [], interesses: [] },
      });
      const { id } = await r.json();
      await page.addInitScript((pid) => localStorage.setItem("sossego.perfil", pid), id);
    });

    test("telas", async ({ page }) => {
      await page.goto("/");
      await expect(cards(page).first()).toBeVisible();
      await foto(page, "01-home");

      await page.goto("/busca?q=ps5");
      await expect(cards(page)).toHaveCount(2);
      await foto(page, "02-busca");

      await page.goto("/busca?q=ps5&ordem=preco&min=1000");
      await expect(cards(page)).toHaveCount(1);
      await foto(page, "03-busca-ordenada-e-filtrada");

      await page.goto("/busca?categoria=jogos-tabuleiro");
      await expect(cards(page)).toHaveCount(2);
      await foto(page, "04-categoria");

      await page.goto("/busca?q=geladeira%20frost%20free");
      await expect(page.getByText(/Nada no histórico/)).toBeVisible();
      await foto(page, "05-busca-sem-resultado");

      await page.goto("/busca?q=mario%20kart");
      await cards(page).first().click();
      await expect(page.getByRole("link", { name: "Ver na loja" }).first()).toBeVisible();
      await foto(page, "06-produto-provisorio");
    });

    test("erro", async ({ page }) => {
      await page.route("**/api/v1/busca?*", (r) => r.fulfill({ status: 503, body: "{}" }));
      await page.goto("/busca?q=ps5");
      await expect(page.getByRole("alert")).toBeVisible();
      await foto(page, "07-busca-erro");
    });
  });
}
