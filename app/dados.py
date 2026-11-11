"""Acesso aos dados da plataforma (arquivos CSV em app/data, carregados uma vez na memória)."""
from __future__ import annotations

import csv
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PASTA = Path(__file__).resolve().parent / "data"

LIMIAR_ATENCAO = 0.30   # na pontuação bruta do modelo; em probabilidade calibrada, ver limiares()
NOME_CULTURA = {"feijao": "feijão", "milho": "milho"}
ROTULO_NIVEL = {"alto": "Risco alto", "atencao": "Atenção", "baixo": "Risco baixo"}
NOME_UF = {
    "AL": "Alagoas", "BA": "Bahia", "CE": "Ceará", "ES": "Espírito Santo", "MA": "Maranhão",
    "MG": "Minas Gerais", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí",
    "RN": "Rio Grande do Norte", "SE": "Sergipe",
}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]
FAIXAS_CHUVA = [(0, 40, "menos de 40%"), (40, 60, "40–60%"), (60, 80, "60–80%"),
                (80, 100, "80–100%"), (100, 120, "100–120%"), (120, 10_000, "mais de 120%")]


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()


def _ler(nome: str) -> List[Dict[str, str]]:
    caminho = PASTA / nome
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe. Rode: python scripts/preparar_app.py")
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(valor: str) -> Optional[float]:
    return float(valor) if valor not in ("", None) else None


@lru_cache(maxsize=1)
def previsoes() -> List[Dict[str, Any]]:
    linhas = []
    for r in _ler("previsoes.csv"):
        prob, alerta = float(r["prob_quebra"]), int(r["alerta"])          # prob: probabilidade calibrada
        pontuacao = float(r["pontuacao"]) if r.get("pontuacao") else prob  # saída bruta, que define o nível
        chuva = _num(r["chuva_estacao_pct_normal"])
        linhas.append({
            "cod_mun": int(r["cod_mun"]), "municipio": r["municipio"], "uf": r["uf"],
            "lat": float(r["latitude"]), "lon": float(r["longitude"]),
            "ano": int(r["ano"]), "cultura": r["cultura"],
            "chuva_pct": None if chuva is None else round(chuva),
            "prob": round(prob, 3),
            "nivel": "alto" if alerta else ("atencao" if pontuacao >= LIMIAR_ATENCAO else "baixo"),
            # vazio = safra ainda sem resultado oficial do IBGE
            "quebra_real": int(r["quebra_real"]) if r["quebra_real"] not in ("", None) else None,
        })
    return linhas


@lru_cache(maxsize=1)
def limiar_alerta() -> float:
    """Menor probabilidade tratada como alerta nas safras já conferidas (limiar do notebook)."""
    return min(d["prob"] for d in previsoes() if d["nivel"] == "alto" and d["quebra_real"] is not None)


@lru_cache(maxsize=1)
def limiares() -> Dict[int, Dict[str, float]]:
    """Onde começam "atenção" e "risco alto" em cada safra, em probabilidade calibrada.

    As safras conferidas (teste do notebook) e a safra atual vêm de ajustes diferentes do modelo,
    cada um com sua calibração; por isso o limite não é o mesmo em todos os anos.
    """
    saida: Dict[int, Dict[str, float]] = {}
    for ano in {d["ano"] for d in previsoes()}:
        do_ano = [d for d in previsoes() if d["ano"] == ano]
        saida[ano] = {nivel: round(min((d["prob"] for d in do_ano if d["nivel"] == nivel), default=0.0), 3)
                      for nivel in ("atencao", "alto")}
    return saida


@lru_cache(maxsize=1)
def anos_sem_resultado() -> List[int]:
    """Safras previstas cujo resultado oficial ainda não saiu."""
    com = {d["ano"] for d in previsoes() if d["quebra_real"] is not None}
    return sorted({d["ano"] for d in previsoes()} - com)


@lru_cache(maxsize=1)
def municipios() -> Dict[int, Dict[str, Any]]:
    saida = {}
    for r in _ler("municipios.csv"):
        cod = int(r["cod_mun"])
        saida[cod] = {
            "cod_mun": cod, "municipio": r["municipio"], "uf": r["uf"],
            "lat": float(r["latitude"]), "lon": float(r["longitude"]),
            "celula": (float(r["cel_lat"]), float(r["cel_lon"])),
            "mes_inicio_chuvas": int(r["mes_inicio_chuvas"]),
            "chuva_normal": [_num(r[f"chuva_normal_{m}"]) for m in range(1, 13)],
            "rend": {"feijao": _num(r["rend_feijao"]), "milho": _num(r["rend_milho"])},
            "area": {"feijao": _num(r["area_feijao"]), "milho": _num(r["area_milho"])},
            "chave": sem_acento(r["municipio"]),
        }
    return saida


@lru_cache(maxsize=1)
def historico() -> List[Dict[str, Any]]:
    return [{"ano": int(r["ano"]), "uf": r["uf"], "cultura": r["cultura"],
             "safras": int(r["safras"]), "quebras": int(r["quebras"]),
             "area_plantada_ha": float(r["area_plantada_ha"]),
             "area_colhida_ha": float(r["area_colhida_ha"]),
             "producao_t": float(r["producao_t"])} for r in _ler("historico.csv")]


# ------------------------------------------------------------------ consultas
def anos() -> List[int]:
    return sorted({d["ano"] for d in previsoes()}, reverse=True)


def culturas() -> List[str]:
    return sorted({d["cultura"] for d in previsoes()}, reverse=True)


def ufs() -> List[str]:
    return sorted({d["uf"] for d in previsoes()})


def filtrar(ano: Optional[int] = None, cultura: Optional[str] = None, uf: Optional[str] = None,
            cod_mun: Optional[int] = None) -> List[Dict[str, Any]]:
    return [d for d in previsoes()
            if (ano is None or d["ano"] == ano)
            and (not cultura or d["cultura"] == cultura)
            and (not uf or d["uf"] == uf)
            and (cod_mun is None or d["cod_mun"] == cod_mun)]


def resumo(linhas: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    linhas = list(linhas)
    altos = [d for d in linhas if d["nivel"] == "alto"]
    conferidas = [d for d in linhas if d["quebra_real"] is not None]
    altos_conferidos = [d for d in conferidas if d["nivel"] == "alto"]
    quebras = [d for d in conferidas if d["quebra_real"]]
    chuvas = [d["chuva_pct"] for d in linhas if d["chuva_pct"] is not None]
    avisadas = sum(1 for d in quebras if d["nivel"] == "alto")
    return {
        "safras": len(linhas),
        "conferidas": len(conferidas),
        "alto": len(altos),
        "atencao": sum(1 for d in linhas if d["nivel"] == "atencao"),
        "baixo": sum(1 for d in linhas if d["nivel"] == "baixo"),
        "chuva_media_pct": round(sum(chuvas) / len(chuvas)) if chuvas else None,
        "quebras_reais": len(quebras),
        "quebras_avisadas": avisadas,
        "alertas_confirmados": sum(1 for d in altos_conferidos if d["quebra_real"]),
        "alertas_conferidos": len(altos_conferidos),
        "recall": round(avisadas / len(quebras), 3) if quebras else None,
        "precisao": (round(sum(1 for d in altos_conferidos if d["quebra_real"]) / len(altos_conferidos), 3)
                     if altos_conferidos else None),
    }


def buscar_municipios(termo: str, limite: int = 8) -> List[Dict[str, Any]]:
    chave = sem_acento(termo.strip())
    if not chave:
        return []
    comeca, contem = [], []
    for m in municipios().values():
        if m["chave"].startswith(chave):
            comeca.append(m)
        elif chave in m["chave"]:
            contem.append(m)
    achados = sorted(comeca, key=lambda m: m["municipio"]) + sorted(contem, key=lambda m: m["municipio"])
    return [{"cod_mun": m["cod_mun"], "municipio": m["municipio"], "uf": m["uf"]} for m in achados[:limite]]


def detalhe_municipio(cod_mun: int, ano: int, cultura: str) -> Optional[Dict[str, Any]]:
    serie = sorted(filtrar(cultura=cultura, cod_mun=cod_mun), key=lambda d: d["ano"])
    atual = next((d for d in serie if d["ano"] == ano), None)
    if atual is None:
        return None
    m = municipios().get(cod_mun, {})
    inicio = m.get("mes_inicio_chuvas")
    return {
        **{k: atual[k] for k in ("cod_mun", "municipio", "uf", "ano", "cultura", "prob", "nivel",
                                  "chuva_pct", "quebra_real", "lat", "lon")},
        "rotulo_nivel": ROTULO_NIVEL[atual["nivel"]],
        "historico": [{k: d[k] for k in ("ano", "prob", "nivel", "quebra_real", "chuva_pct")} for d in serie],
        "mes_inicio_chuvas": inicio,
        "estacao": [MESES[(inicio - 1 + k) % 12] for k in range(4)] if inicio else [],
        "chuva_normal": m.get("chuva_normal"),
        "rend_habitual": (m.get("rend") or {}).get(cultura),
        "area_habitual": (m.get("area") or {}).get(cultura),
    }


def analises(cultura: Optional[str] = None, uf: Optional[str] = None) -> Dict[str, Any]:
    """Tudo o que a página de análises precisa, já agregado."""
    # 1. histórico real de quebras (IBGE), 2003–2025
    por_ano: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for h in historico():
        if (cultura and h["cultura"] != cultura) or (uf and h["uf"] != uf):
            continue
        a = por_ano[h["ano"]]
        for k in ("safras", "quebras", "area_plantada_ha", "area_colhida_ha", "producao_t"):
            a[k] += h[k]
    serie_hist = [{"ano": ano, "safras": int(v["safras"]), "quebras": int(v["quebras"]),
                   "taxa": round(100 * v["quebras"] / v["safras"], 1) if v["safras"] else 0,
                   "area_plantada_ha": round(v["area_plantada_ha"]),
                   "area_colhida_ha": round(v["area_colhida_ha"]),
                   "producao_t": round(v["producao_t"])}
                  for ano, v in sorted(por_ano.items())]

    todas = filtrar(cultura=cultura, uf=uf)
    # acerto do modelo só pode ser medido nas safras que já têm resultado oficial
    base = [d for d in todas if d["quebra_real"] is not None]

    # 2. alertas x quebras por ano (inclui a safra atual, só com os alertas)
    por_ano_teste = []
    for ano in sorted({d["ano"] for d in todas}):
        r = resumo(d for d in todas if d["ano"] == ano)
        por_ano_teste.append({"ano": ano, **r})

    # 3. por estado (sempre todos os estados, para permitir comparar e clicar)
    por_uf = []
    todos = [d for d in filtrar(cultura=cultura) if d["quebra_real"] is not None]
    for sigla in sorted({d["uf"] for d in todos}):
        r = resumo(d for d in todos if d["uf"] == sigla)
        por_uf.append({"uf": sigla, "nome": NOME_UF.get(sigla, sigla),
                       "taxa_quebra": round(r["quebras_reais"] / r["safras"], 3) if r["safras"] else None,
                       **r})

    # 4. chuva x quebra
    faixas = []
    for minimo, maximo, rotulo in FAIXAS_CHUVA:
        grupo = [d for d in base if d["chuva_pct"] is not None and minimo <= d["chuva_pct"] < maximo]
        faixas.append({"faixa": rotulo, "safras": len(grupo),
                       "taxa": round(100 * sum(d["quebra_real"] for d in grupo) / len(grupo), 1) if grupo else None})

    # 5. distribuição das probabilidades (para o simulador de limiar), em 100 faixas de 0,01
    quebrou, normal = [0] * 100, [0] * 100
    for d in base:
        i = min(int(d["prob"] * 100), 99)
        (quebrou if d["quebra_real"] else normal)[i] += 1

    return {
        "historico": serie_hist,
        "teste_por_ano": por_ano_teste,
        "por_uf": por_uf,
        "chuva": faixas,
        "distribuicao": {"quebrou": quebrou, "normal": normal, "passo": 0.01},
        "limiar_modelo": limiar_alerta(),
        "resumo": resumo(base),
        "anos_sem_resultado": anos_sem_resultado(),
    }
