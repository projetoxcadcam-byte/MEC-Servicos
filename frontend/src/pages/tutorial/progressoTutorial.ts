import type { PerfilTutorial } from "./dadosTutorial";

export type ProgressoTutorial = { versao: 1; lidas: string[]; ultima: string };
type Armazenamento = Pick<Storage, "getItem" | "setItem">;

export function chaveTutorial(usuario: number, perfil: PerfilTutorial, empresa: number | null): string {
  return `mec-tutorial-d66:v1:${usuario}:${perfil}:${empresa ?? "administracao"}`;
}

export function lerProgresso(armazenamento: Armazenamento | undefined, chave: string, permitidas: string[]): ProgressoTutorial {
  const inicial: ProgressoTutorial = { versao: 1, lidas: [], ultima: permitidas[0] ?? "" };
  try {
    const salvo: unknown = JSON.parse(armazenamento?.getItem(chave) ?? "null");
    if (!salvo || typeof salvo !== "object" || !("versao" in salvo) || salvo.versao !== 1) return inicial;
    const valor = salvo as Partial<ProgressoTutorial>;
    return {
      versao: 1,
      lidas: Array.isArray(valor.lidas) ? [...new Set(valor.lidas.filter(id => typeof id === "string" && permitidas.includes(id)))] : [],
      ultima: typeof valor.ultima === "string" && permitidas.includes(valor.ultima) ? valor.ultima : inicial.ultima,
    };
  } catch { return inicial; }
}

export function salvarProgresso(armazenamento: Armazenamento | undefined, chave: string, valor: ProgressoTutorial): boolean {
  if (!armazenamento) return false;
  try { armazenamento.setItem(chave, JSON.stringify(valor)); return true; }
  catch { return false; }
}
