"""Variáveis e modelo do Safra Sentinela, fora do notebook.

Repete, linha a linha, a construção de variáveis das seções 3.2 a 3.5 do notebook
(notebook/Safra_Sentinela_ML.py), para que a previsão da safra atual use exatamente o mesmo
modelo. `scripts/prever_safra_atual.py` confere essa equivalência antes de prever.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

SEED = 42
ANO_CORTE_ESTACAO = 2019          # o calendário das chuvas usa só os anos de treino do notebook
CEL = ["cel_lat", "cel_lon"]
VARS_MES = ["chuva_mm", "chuva_desvio_mm", "umidade_solo_raiz", "solo_desvio",
            "temp_max_desvio_c", "umidade_rel_pct"]
MESES_REL = {-3: "pre3", -2: "pre2", -1: "pre1", 0: "m1", 1: "m2", 2: "m3", 3: "m4"}
CATEGORICAS = ["cultura", "uf"]
HISTORICO = ["rend_ref", "rend_ano_anterior", "rend_variabilidade", "quebras_5_anos",
             "log_area_plantada_ant", "latitude", "longitude", "mes_inicio_chuvas"]
NUMERICAS = (HISTORICO
             + [f"{v}_{r}" for r in ("pre3", "pre2", "pre1") for v in VARS_MES]
             + ["chuva_pre_mm", "chuva_pre_pct_normal"]
             + [f"{v}_{r}" for r in ("m1", "m2") for v in VARS_MES]
             + ["chuva_m1m2_mm", "chuva_m1m2_pct_normal"]
             + [f"{v}_{r}" for r in ("m3", "m4") for v in VARS_MES]
             + ["chuva_estacao_mm", "chuva_estacao_pct_normal"])
PREDITORAS = NUMERICAS + CATEGORICAS
# hiperparâmetros escolhidos pela validação cruzada do notebook (seção 5)
HIPER = {"learning_rate": 0.03, "max_leaf_nodes": 8}


def normal_anterior(serie):
    return serie.shift(1).expanding(min_periods=3).mean()


def montar_base(municipios: pd.DataFrame, producao: pd.DataFrame, clima: pd.DataFrame,
                ano_previsao: int | None = None) -> pd.DataFrame:
    """Devolve a base município–ano–cultura com alvo e preditoras.

    Com `ano_previsao`, acrescenta as lavouras daquele ano (as que tiveram plantio no ano
    anterior), sem alvo: é a safra que ainda não tem resultado oficial.
    """
    clima = clima.sort_values(CEL + ["ano", "mes"]).reset_index(drop=True).copy()
    dias = pd.to_datetime(dict(year=clima["ano"], month=clima["mes"], day=1)).dt.days_in_month
    clima["chuva_mm"] = clima["chuva_mm_dia"] * dias
    clima["t"] = clima["ano"] * 12 + clima["mes"] - 1

    normal = clima[clima["ano"] <= ANO_CORTE_ESTACAO].groupby(CEL + ["mes"])["chuva_mm"].mean().unstack()
    janelas = pd.concat({ini: normal[[(ini + k - 1) % 12 + 1 for k in range(4)]].sum(axis=1)
                         for ini in range(1, 13)}, axis=1)
    estacao = janelas.idxmax(axis=1).rename("mes_inicio_chuvas").reset_index()
    mun_est = municipios.merge(estacao, on=CEL)

    por_mes = clima.groupby(CEL + ["mes"])
    clima["chuva_desvio_mm"] = clima["chuva_mm"] - por_mes["chuva_mm"].transform(normal_anterior)
    clima["solo_desvio"] = clima["umidade_solo_raiz"] - por_mes["umidade_solo_raiz"].transform(normal_anterior)
    clima["temp_max_desvio_c"] = clima["temp_max_c"] - por_mes["temp_max_c"].transform(normal_anterior)

    ultimo_ano = max(int(clima["ano"].max()), ano_previsao or 0)
    grade = estacao.merge(pd.DataFrame({"ano": range(1996, ultimo_ano + 1)}), how="cross")
    grade["t0"] = (np.where(grade["mes_inicio_chuvas"] >= 10, grade["ano"] - 1, grade["ano"]) * 12
                   + grade["mes_inicio_chuvas"] - 1)
    partes = []
    for desloc, rotulo in MESES_REL.items():
        partes.append(grade.assign(t=grade["t0"] + desloc)
                      .merge(clima[CEL + ["t"] + VARS_MES], on=CEL + ["t"], how="left")
                      .set_index(CEL + ["ano"])[VARS_MES].add_suffix(f"_{rotulo}"))
    cs = pd.concat(partes, axis=1).reset_index().sort_values(CEL + ["ano"])
    cs["chuva_pre_mm"] = cs[[f"chuva_mm_{m}" for m in ("pre3", "pre2", "pre1")]].sum(axis=1, min_count=3)
    cs["chuva_m1m2_mm"] = cs[["chuva_mm_m1", "chuva_mm_m2"]].sum(axis=1, min_count=2)
    cs["chuva_estacao_mm"] = cs[[f"chuva_mm_m{i}" for i in range(1, 5)]].sum(axis=1, min_count=4)
    for v in ("chuva_pre", "chuva_m1m2", "chuva_estacao"):
        ref = cs.groupby(CEL)[f"{v}_mm"].transform(normal_anterior)
        cs[f"{v}_pct_normal"] = 100 * cs[f"{v}_mm"] / ref

    producao = producao.copy()
    if ano_previsao:
        anterior = producao[producao["ano"] == ano_previsao - 1]
        futuro = anterior[["cod_mun", "municipio", "uf", "cultura"]].assign(ano=ano_previsao)
        producao = pd.concat([producao, futuro], ignore_index=True)
    producao = producao.sort_values(["cod_mun", "cultura", "ano"]).reset_index(drop=True)
    serie = producao.groupby(["cod_mun", "cultura"])
    producao["rend_ref"] = serie["rendimento_kg_ha"].transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    producao["rend_ano_anterior"] = serie["rendimento_kg_ha"].shift(1)
    producao["rend_variabilidade"] = serie["rendimento_kg_ha"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=3).std()) / producao["rend_ref"]
    producao["log_area_plantada_ant"] = np.log1p(serie["area_plantada_ha"].shift(1))
    producao["quebra"] = (producao["rendimento_kg_ha"] < 0.5 * producao["rend_ref"]).astype(int)
    producao["quebras_5_anos"] = (producao.groupby(["cod_mun", "cultura"])["quebra"]
                                  .transform(lambda s: s.shift(1).rolling(5, min_periods=1).sum()))
    if ano_previsao:
        producao.loc[producao["ano"] == ano_previsao, "quebra"] = np.nan

    return (producao[producao["rend_ref"] > 0]
            .merge(mun_est.drop(columns=["municipio", "uf"]), on="cod_mun")
            .merge(cs, on=CEL + ["ano"], how="left")
            .sort_values(["ano", "cod_mun", "cultura"]).reset_index(drop=True))


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class CalibradorPlatt:
    """Calibração de Platt: p = sigmoide(a × logit(pontuação) + b).

    Ajustada com previsões fora da amostra. É estritamente crescente, então não muda a ordem das
    lavouras; só converte a pontuação (inflada pelos pesos de classe) em probabilidade.
    """

    def fit(self, pontuacao, y) -> "CalibradorPlatt":
        self._reg = LogisticRegression(C=1e6, max_iter=1000).fit(logit(pontuacao).reshape(-1, 1), y)
        self.a, self.b = float(self._reg.coef_[0, 0]), float(self._reg.intercept_[0])
        return self

    def __call__(self, pontuacao):
        return self._reg.predict_proba(logit(pontuacao).reshape(-1, 1))[:, 1]


def erro_calibracao(y, p, faixas: int = 10) -> float:
    """ECE por decis: média ponderada de |frequência observada − probabilidade média|."""
    tab = (pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
           .assign(faixa=lambda d: pd.qcut(d["p"], faixas, duplicates="drop"))
           .groupby("faixa", observed=True).agg(y=("y", "mean"), p=("p", "mean"), n=("y", "size")))
    return float((tab["n"] / tab["n"].sum() * (tab["y"] - tab["p"]).abs()).sum())


def criar_modelo() -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("imputar", SimpleImputer(strategy="median"))]), NUMERICAS),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAS),
    ])
    modelo = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=SEED, **HIPER)
    return Pipeline([("pre", pre), ("modelo", modelo)])
