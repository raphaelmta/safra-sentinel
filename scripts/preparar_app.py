"""Prepara os dados que a plataforma web consome (pasta app/data).

Entradas: data/*.csv (scripts/coletar_dados.py) e notebook/previsoes_teste.csv (notebook de ML).
Saídas:   app/data/previsoes.csv, app/data/historico.csv, app/data/municipios.csv

Uso: python scripts/preparar_app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DATA, SAIDA = RAIZ / "data", RAIZ / "app" / "data"
CEL = ["cel_lat", "cel_lon"]


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    # safras conferidas (teste do notebook) + safra atual, ainda sem resultado oficial
    partes = [pd.read_csv(RAIZ / "notebook" / "previsoes_teste.csv")]
    for arq in sorted(DATA.glob("previsoes_safra_*.csv")):
        partes.append(pd.read_csv(arq))
    previsoes = pd.concat(partes, ignore_index=True)
    previsoes["quebra_real"] = previsoes["quebra_real"].astype("Int64")
    previsoes.to_csv(SAIDA / "previsoes.csv", index=False, float_format="%.4f")

    pam = pd.read_csv(DATA / "producao_pam.csv").sort_values(["cod_mun", "cultura", "ano"])
    serie = pam.groupby(["cod_mun", "cultura"])["rendimento_kg_ha"]
    pam["rend_ref"] = serie.transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    base = pam[pam["rend_ref"] > 0].copy()
    base["quebra"] = (base["rendimento_kg_ha"] < 0.5 * base["rend_ref"]).astype(int)

    # Histórico real de quebras por ano, estado e cultura (mesma definição do notebook)
    historico = (base.groupby(["ano", "uf", "cultura"])
                 .agg(safras=("quebra", "size"), quebras=("quebra", "sum"),
                      area_plantada_ha=("area_plantada_ha", "sum"),
                      area_colhida_ha=("area_colhida_ha", "sum"),
                      producao_t=("producao_t", "sum"))
                 .reset_index())
    historico.to_csv(SAIDA / "historico.csv", index=False)

    # Municípios: calendário das chuvas e rendimento habitual (média das 5 últimas safras)
    clima = pd.read_csv(DATA / "clima_mensal.csv")
    dias = pd.to_datetime(dict(year=clima["ano"], month=clima["mes"], day=1)).dt.days_in_month
    clima["chuva_mm"] = clima["chuva_mm_dia"] * dias
    normal = clima[clima["ano"] <= 2019].groupby(CEL + ["mes"])["chuva_mm"].mean().unstack()
    janelas = pd.concat({i: normal[[(i + k - 1) % 12 + 1 for k in range(4)]].sum(axis=1)
                         for i in range(1, 13)}, axis=1)
    estacao = janelas.idxmax(axis=1).rename("mes_inicio_chuvas").reset_index()
    chuva_normal = normal.round(0).add_prefix("chuva_normal_").reset_index()

    recentes = pam[pam["ano"] >= pam["ano"].max() - 4]
    habitual = (recentes.groupby(["cod_mun", "cultura"])
                .agg(rend=("rendimento_kg_ha", "mean"), area=("area_plantada_ha", "mean"))
                .round(0).unstack("cultura"))
    habitual.columns = [f"{a}_{b}" for a, b in habitual.columns]

    mun = (pd.read_csv(DATA / "municipios_semiarido.csv")
           .merge(estacao, on=CEL).merge(chuva_normal, on=CEL)
           .merge(habitual.reset_index(), on="cod_mun", how="left"))
    mun.to_csv(SAIDA / "municipios.csv", index=False)
    print(f"previsoes: {sum(1 for _ in open(SAIDA / 'previsoes.csv')) - 1} linhas | "
          f"historico: {len(historico)} | municipios: {len(mun)}")


if __name__ == "__main__":
    main()
