"""Coleta das bases públicas do projeto Safra Sentinela.

Fontes:
  1. IBGE – lista oficial dos municípios do Semiárido (delimitação 2022)
  2. IBGE/SIDRA – Produção Agrícola Municipal (PAM), tabela 5457
  3. NASA POWER – climatologia mensal por ponto (grade MERRA-2 0,5° x 0,625°)
  4. Coordenadas das sedes municipais (github.com/kelvins/municipios-brasileiros)

Saídas (em data/):
  municipios_semiarido.csv, producao_pam.csv, clima_mensal.csv

Uso: python scripts/coletar_dados.py
As respostas brutas ficam em data/raw/ (cache): rodar de novo não baixa tudo outra vez.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
RAW = DATA / "raw"

ANO_INI, ANO_FIM = 2000, 2025          # safras analisadas (PAM)
CLIMA_INI = 1995                        # clima começa antes para permitir defasagens
CULTURAS = {"40112": "feijao", "40122": "milho"}
VARIAVEIS = {
    "8331": "area_plantada_ha",
    "216": "area_colhida_ha",
    "214": "producao_t",
    "112": "rendimento_kg_ha",
}
PARAMS_CLIMA = ["PRECTOTCORR", "T2M_MAX", "T2M_MIN", "RH2M", "GWETROOT", "WS2M"]

URL_SEMIARIDO = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/"
    "semiarido_brasileiro/Situacao_2022/lista_municipios_Semiarido_2022.xlsx"
)
URL_COORD = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
UF = {21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
      28: "SE", 29: "BA", 31: "MG", 32: "ES"}

sessao = requests.Session()
sessao.headers["User-Agent"] = "safra-sentinela-coleta/1.0"


def baixar(url: str, destino: Path, tentativas: int = 5, **kw) -> Path:
    """Baixa a URL para `destino` (se ainda não existir), com novas tentativas."""
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tentativas):
        try:
            r = sessao.get(url, timeout=180, **kw)
            r.raise_for_status()
            destino.write_bytes(r.content)
            return destino
        except requests.RequestException as e:
            if i == tentativas - 1:
                raise
            time.sleep(3 * (i + 1))
            print(f"  nova tentativa ({i + 1}) para {destino.name}: {e}")
    return destino


# ---------------------------------------------------------------- municípios
def municipios() -> pd.DataFrame:
    xlsx = baixar(URL_SEMIARIDO, RAW / "lista_municipios_Semiarido_2022.xlsx")
    coord = baixar(URL_COORD, RAW / "municipios_coordenadas.csv")
    semi = pd.read_excel(xlsx, dtype={"CD_MUN": int})[["CD_MUN"]]
    c = pd.read_csv(coord)[["codigo_ibge", "nome", "latitude", "longitude"]]
    df = semi.merge(c, left_on="CD_MUN", right_on="codigo_ibge", how="left")
    faltam = df["latitude"].isna().sum()
    if faltam:
        print(f"  aviso: {faltam} municípios sem coordenada foram descartados")
        df = df.dropna(subset=["latitude"])
    df = df.rename(columns={"CD_MUN": "cod_mun", "nome": "municipio"})
    df["uf"] = (df["cod_mun"] // 100000).map(UF)
    # célula da grade MERRA-2 usada pelo NASA POWER (0,5° lat x 0,625° lon)
    df["cel_lat"] = (df["latitude"] / 0.5).round() * 0.5
    df["cel_lon"] = (df["longitude"] / 0.625).round() * 0.625
    df = df[["cod_mun", "municipio", "uf", "latitude", "longitude", "cel_lat", "cel_lon"]]
    return df.sort_values("cod_mun").reset_index(drop=True)


# ----------------------------------------------------------------------- PAM
def pam(mun: pd.DataFrame) -> pd.DataFrame:
    anos = list(range(ANO_INI, ANO_FIM + 1))
    blocos = [anos[i:i + 9] for i in range(0, len(anos), 9)]  # < 100 mil valores/req
    ufs = sorted((mun["cod_mun"] // 100000).unique())
    partes = []
    for cod_cult, cultura in CULTURAS.items():
        for uf in ufs:
            for b in blocos:
                url = (
                    f"https://apisidra.ibge.gov.br/values/t/5457/n6/in%20n3%20{uf}"
                    f"/v/{','.join(VARIAVEIS)}/p/{b[0]}-{b[-1]}/c782/{cod_cult}"
                )
                arq = baixar(url, RAW / "sidra" / f"pam_{cultura}_{uf}_{b[0]}_{b[-1]}.json")
                linhas = json.loads(arq.read_text())[1:]  # 1ª linha é o cabeçalho
                d = pd.DataFrame(linhas)[["D1C", "D2C", "D3C", "V"]]
                d["cultura"] = cultura
                partes.append(d)
        print(f"  PAM {cultura}: ok")
    df = pd.concat(partes, ignore_index=True)
    df.columns = ["cod_mun", "var", "ano", "valor", "cultura"]
    df["cod_mun"] = df["cod_mun"].astype(int)
    df["ano"] = df["ano"].astype(int)
    df = df[df["cod_mun"].isin(mun["cod_mun"])]
    # Convenções do SIDRA: "-" = zero absoluto; "..." = não disponível; "X" = sigilo.
    # O zero é mantido como 0; os demais símbolos viram ausentes (NaN).
    df["valor"] = pd.to_numeric(df["valor"].replace("-", "0"), errors="coerce")
    df["var"] = df["var"].map(VARIAVEIS)
    df = (df.pivot_table(index=["cod_mun", "ano", "cultura"], columns="var",
                         values="valor", dropna=False)
            .reset_index())
    df.columns.name = None
    # sem área plantada não houve safra: a linha não tem rendimento a prever
    df = df[df["area_plantada_ha"].fillna(0) > 0]
    df = df.merge(mun[["cod_mun", "municipio", "uf"]], on="cod_mun")
    cols = ["cod_mun", "municipio", "uf", "ano", "cultura", *VARIAVEIS.values()]
    return df[cols].sort_values(["cod_mun", "cultura", "ano"]).reset_index(drop=True)


# --------------------------------------------------------------------- clima
def _celula(lat: float, lon: float) -> Path:
    url = (
        "https://power.larc.nasa.gov/api/temporal/monthly/point"
        f"?parameters={','.join(PARAMS_CLIMA)}&community=AG"
        f"&longitude={lon}&latitude={lat}&start={CLIMA_INI}&end={ANO_FIM}&format=JSON"
    )
    return baixar(url, RAW / "power" / f"power_{lat:+.3f}_{lon:+.3f}.json")


def clima(mun: pd.DataFrame) -> pd.DataFrame:
    celulas = mun[["cel_lat", "cel_lon"]].drop_duplicates().itertuples(index=False)
    celulas = [(float(a), float(b)) for a, b in celulas]
    print(f"  NASA POWER: {len(celulas)} células de grade")
    with ThreadPoolExecutor(max_workers=4) as ex:
        arquivos = list(ex.map(lambda c: _celula(*c), celulas))
    partes = []
    for (lat, lon), arq in zip(celulas, arquivos):
        p = json.loads(arq.read_text())["properties"]["parameter"]
        d = pd.DataFrame(p)
        d = d[~d.index.str.endswith("13")]  # "AAAA13" é a média anual
        d.insert(0, "mes", d.index.str[4:].astype(int))
        d.insert(0, "ano", d.index.str[:4].astype(int))
        d.insert(0, "cel_lon", lon)
        d.insert(0, "cel_lat", lat)
        partes.append(d)
    df = pd.concat(partes, ignore_index=True)
    df[PARAMS_CLIMA] = df[PARAMS_CLIMA].mask(df[PARAMS_CLIMA] <= -999)  # -999 = ausente
    df = df.rename(columns={
        "PRECTOTCORR": "chuva_mm_dia", "T2M_MAX": "temp_max_c", "T2M_MIN": "temp_min_c",
        "RH2M": "umidade_rel_pct", "GWETROOT": "umidade_solo_raiz", "WS2M": "vento_ms",
    })
    return df.sort_values(["cel_lat", "cel_lon", "ano", "mes"]).reset_index(drop=True)


def main() -> None:
    DATA.mkdir(exist_ok=True)
    print("1/3 municípios do Semiárido")
    mun = municipios()
    mun.to_csv(DATA / "municipios_semiarido.csv", index=False)
    print(f"  {len(mun)} municípios")
    print("2/3 produção agrícola (IBGE PAM)")
    p = pam(mun)
    p.to_csv(DATA / "producao_pam.csv", index=False)
    print(f"  {len(p)} linhas município-ano-cultura")
    print("3/3 clima mensal (NASA POWER)")
    c = clima(mun)
    c.to_csv(DATA / "clima_mensal.csv", index=False)
    print(f"  {len(c)} linhas célula-mês")


if __name__ == "__main__":
    main()
