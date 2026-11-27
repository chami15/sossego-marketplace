export function BarraProgresso({ passo, total }: { passo: number; total: number }) {
  return (
    <div
      className="progresso"
      role="progressbar"
      aria-label="Progresso"
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={passo}
      aria-valuetext={`passo ${passo} de ${total}`}
    >
      <div className="progresso__preenchido" style={{ width: `${(passo / total) * 100}%` }} />
    </div>
  );
}
