"""Operações selecionáveis para a legenda; não determinam a sequência de execução."""
from typing import Literal

OperacaoPdf = Literal[
    "usinagem", "torneamento", "fresamento", "furacao", "rosqueamento",
    "mandrilamento", "chaveta", "retifica", "eletroerosao_fio", "eletroerosao_penetracao",
    "corte_serra", "corte_laser", "corte_plasma", "corte_agua", "oxicorte",
    "dobra", "calandragem", "estampagem", "solda_mig_mag", "solda_tig",
    "solda_eletrodo", "brasagem", "pintura_liquida", "pintura_po", "jateamento",
    "polimento", "anodizacao", "galvanizacao", "tratamento_termico", "montagem",
]

OPERACOES_PDF = {
    "usinagem": "Usinagem", "torneamento": "Torneamento", "fresamento": "Fresamento",
    "furacao": "Furacao", "rosqueamento": "Rosqueamento", "mandrilamento": "Mandrilamento",
    "chaveta": "Rasgo de chaveta", "retifica": "Retifica", "eletroerosao_fio": "Eletroerosao a fio",
    "eletroerosao_penetracao": "Eletroerosao por penetracao", "corte_serra": "Corte por serra",
    "corte_laser": "Corte a laser", "corte_plasma": "Corte a plasma", "corte_agua": "Corte por jato d'agua",
    "oxicorte": "Oxicorte", "dobra": "Dobra", "calandragem": "Calandragem", "estampagem": "Estampagem",
    "solda_mig_mag": "Solda MIG/MAG", "solda_tig": "Solda TIG", "solda_eletrodo": "Solda com eletrodo",
    "brasagem": "Brasagem", "pintura_liquida": "Pintura liquida", "pintura_po": "Pintura a po",
    "jateamento": "Jateamento", "polimento": "Polimento", "anodizacao": "Anodizacao",
    "galvanizacao": "Galvanizacao", "tratamento_termico": "Tratamento termico", "montagem": "Montagem",
}

MAX_OPERACOES_PDF = 8
