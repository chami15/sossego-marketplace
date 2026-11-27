-- 002: ativação das lojas na Black Friday (27/11/2026).
-- Kabum entrou no worker em 26/11 (recon aprovado pelo dono).
-- Amazon: desafio Akamai (bm-verify) às 15:11; o dono desligou até segunda
-- 30/11, quando decide se faz 1 tentativa manual (docs/backlog.md).
UPDATE loja SET coleta_ativa = true  WHERE slug = 'kabum';
UPDATE loja SET coleta_ativa = false WHERE slug = 'amazon';
