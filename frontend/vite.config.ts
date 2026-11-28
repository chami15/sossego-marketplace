import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// A API roda à parte (.\sossego.ps1 api), na 8020: a 8000 é do hub_agente do dono.
// O e2e aponta outra porta, com banco próprio.
const api = process.env.SOSSEGO_API ?? "http://127.0.0.1:8020";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: Number(process.env.SOSSEGO_WEB_PORTA ?? 5173),
    strictPort: true,
    proxy: { "/api": api },
  },
});
