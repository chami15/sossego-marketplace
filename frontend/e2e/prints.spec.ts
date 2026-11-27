import { expect, test, type Page } from "@playwright/test";

// Prints para o dono aprovar o visual (desktop 1440 e celular 390), com a API
// de verdade no banco de e2e. Saem em docs/prints/fase-06/.
const TELAS = [
  { nome: "desktop", viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
  { nome: "mobile", viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 },
];

const chip = (p: Page, nome: string) => p.getByRole("button", { name: nome, exact: true });

for (const tela of TELAS) {
  test.describe(tela.nome, () => {
    // Sem transição: o print não pega botão no meio da animação.
    test.use({ viewport: tela.viewport, deviceScaleFactor: tela.deviceScaleFactor, reducedMotion: "reduce" });

    // Página inteira com elemento fixo sai torta (barra no meio, rodapé por cima do
    // conteúdo). Só no print, barra e rodapé entram no fluxo da página; na tela não muda.
    const foto = async (page: Page, n: string) => {
      const estilo = await page.addStyleTag({
        content: ".progresso{position:absolute}.onb__rodape{position:static}",
      });
      await page.screenshot({ path: `../docs/prints/fase-06/${tela.nome}-${n}.png`, fullPage: true });
      await estilo.evaluate((e) => (e as Element).remove());
    };

    test("fluxo", async ({ page }) => {
      await page.goto("/onboarding");
      await expect(page.getByRole("heading", { name: "Sobre você" })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await foto(page, "01-passo1-vazio");

      await chip(page, "25–34").click();
      await chip(page, "Prefiro não dizer").click();
      await foto(page, "02-passo1-selecionado");
      await page.getByRole("button", { name: "Avançar" }).click();

      await expect(page.getByRole("heading", { name: "O que você procura?" })).toBeVisible();
      for (const c of ["Games", "Jogos de tabuleiro", "Informática"]) await chip(page, c).click();
      const termos = page.getByLabel("Tem algo específico em mente?");
      await termos.fill("PS5,Dixit,");
      await page.getByRole("heading").click(); // tira o foco do campo
      await foto(page, "03-passo2-selecionado");
      await chip(page, "Livros").click();
      await expect(page.getByRole("status")).toBeVisible();
      await foto(page, "04-passo2-limite-de-3");
      await page.getByRole("button", { name: "Avançar" }).click();

      await expect(page.getByRole("heading", { name: "Lojas de confiança" })).toBeVisible();
      await foto(page, "05-passo3-sem-preferencia");
      for (const l of ["Kabum", "Ludopedia", "Ri Happy"]) await chip(page, l).click();
      await foto(page, "06-passo3-selecionado");
      await chip(page, "Amazon").click();
      await expect(page.getByRole("status")).toBeVisible();
      await foto(page, "07-passo3-limite-de-3");

      await page.route("**/api/v1/perfis", (r) => r.fulfill({ status: 500, body: "{}" }));
      await page.getByRole("button", { name: "Concluir" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await foto(page, "08-erro-ao-salvar");

      await page.unroute("**/api/v1/perfis");
      await page.getByRole("button", { name: "Tentar de novo" }).click();
      await expect(page.getByRole("heading", { name: /Pronto/ })).toBeVisible();
      await foto(page, "10-pronto");
    });

    test("erro ao carregar opções", async ({ page }) => {
      await page.route("**/api/v1/lojas", (r) => r.fulfill({ status: 503, body: "{}" }));
      await page.goto("/onboarding");
      await chip(page, "18–24").click();
      await page.getByRole("button", { name: "Avançar" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await foto(page, "09-erro-ao-carregar");
    });
  });
}

