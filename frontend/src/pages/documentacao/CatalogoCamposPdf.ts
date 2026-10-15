// Opções de preenchimento. A especificação do material continua sendo conferida pelo administrador.
export const MATERIAIS_PDF = [
  "Aço carbono SAE 1010", "Aço carbono SAE 1020", "Aço carbono SAE 1045", "Aço carbono SAE 1060",
  "Aço liga SAE 4140", "Aço liga SAE 4340", "Aço liga SAE 8620",
  "Aço ferramenta AISI D2", "Aço ferramenta AISI D6", "Aço ferramenta AISI H13",
  "Aço ferramenta AISI O1", "Aço ferramenta AISI P20", "Aço ferramenta 1.2083",
  "Aço inox AISI 303", "Aço inox AISI 304", "Aço inox AISI 304L", "Aço inox AISI 316",
  "Aço inox AISI 316L", "Aço inox AISI 410", "Aço inox AISI 420", "Aço inox AISI 430",
  "Aço inox 17-4 PH", "Aço inox duplex 2205",
  "Alumínio 1050", "Alumínio 1100", "Alumínio 5052", "Alumínio 5083", "Alumínio 6061",
  "Alumínio 6063", "Alumínio 6082", "Alumínio 7075",
  "Ferro fundido cinzento", "Ferro fundido nodular", "Latão", "Bronze", "Bronze-alumínio",
  "Cobre", "Titânio grau 2", "Titânio grau 5",
  "Nylon / PA6", "Nylon / PA66", "Acetal / POM", "Polietileno / PEAD", "Polietileno / UHMW",
  "PTFE", "PVC", "Polipropileno / PP", "Policarbonato / PC", "PEEK", "ABS",
];

export const GRUPOS_OPERACOES_PDF = [
  { nome: "Usinagem", opcoes: [
    ["usinagem", "Usinagem"], ["torneamento", "Torneamento"], ["fresamento", "Fresamento"],
    ["furacao", "Furação"], ["rosqueamento", "Rosqueamento"], ["mandrilamento", "Mandrilamento"],
    ["chaveta", "Rasgo de chaveta"], ["retifica", "Retífica"], ["eletroerosao_fio", "Eletroerosão a fio"],
    ["eletroerosao_penetracao", "Eletroerosão por penetração"],
  ] },
  { nome: "Corte e conformação", opcoes: [
    ["corte_serra", "Corte por serra"], ["corte_laser", "Corte a laser"], ["corte_plasma", "Corte a plasma"],
    ["corte_agua", "Corte por jato d'água"], ["oxicorte", "Oxicorte"], ["dobra", "Dobra"],
    ["calandragem", "Calandragem"], ["estampagem", "Estampagem"],
  ] },
  { nome: "Solda", opcoes: [
    ["solda_mig_mag", "Solda MIG/MAG"], ["solda_tig", "Solda TIG"], ["solda_eletrodo", "Solda com eletrodo"], ["brasagem", "Brasagem"],
  ] },
  { nome: "Pintura e acabamento", opcoes: [
    ["pintura_liquida", "Pintura líquida"], ["pintura_po", "Pintura a pó"], ["jateamento", "Jateamento"],
    ["polimento", "Polimento"], ["anodizacao", "Anodização"], ["galvanizacao", "Galvanização"],
  ] },
  { nome: "Outros serviços", opcoes: [["tratamento_termico", "Tratamento térmico"], ["montagem", "Montagem"]] },
] as const;

export type OperacaoPdf = typeof GRUPOS_OPERACOES_PDF[number]["opcoes"][number][0];
export const OPERACOES_PDF = GRUPOS_OPERACOES_PDF.flatMap(g => g.opcoes.map(([codigo, nome]) => ({ codigo, nome })));
export const MAX_OPERACOES_PDF = 8;

export function opcoesMaterialPdf(historico: string[]): string[] {
  const chaves = new Set<string>();
  return [...historico, ...MATERIAIS_PDF].filter(valor => {
    const chave = valor.trim().replace(/\s+/g, " ").toLowerCase();
    if (chaves.has(chave)) return false;
    chaves.add(chave); return true;
  });
}
