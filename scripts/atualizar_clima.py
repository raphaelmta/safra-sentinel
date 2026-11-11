"""Atualiza os dados de clima mais recentes (NASA POWER).

1. Clima mensal consolidado do ano corrente (o mesmo produto usado no treino), para as variáveis
   do modelo → data/clima_mensal_<ano>.csv
2. Chuva diária dos últimos 120 dias, quase em tempo real → app/data/chuva_diaria.csv

Uso: python scripts/atualizar_clima.py [ano]
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app import clima as clima_app  # noqa: E402

PARAMS = {"PRECTOTCORR": "chuva_mm_dia", "T2M_MAX": "temp_max_c", "T2M_MIN": "temp_min_c",
          "RH2M": "umidade_rel_pct", "GWETROOT": "umidade_solo_raiz", "WS2M": "vento_ms"}


def mensal(ano: int) -> pd.DataFrame:
    mun = pd.read_csv(RAIZ / "data" / "municipios_semiarido.csv")
    celulas = [tuple(map(float, c)) for c in mun[["cel_lat", "cel_lon"]].drop_duplicates().itertuples(index=False)]
    sessao = requests.Session()
    sessao.headers["User-Agent"] = "safra-sentinela-coleta/1.0"

    def uma(c):
        lat, lon = c
        url = ("https://power.larc.nasa.gov/api/temporal/monthly/point"
               f"?parameters={','.join(PARAMS)}&community=AG&longitude={lon}&latitude={lat}"
               f"&start={ano}&end={ano}&format=JSON")
        for i in range(5):
            try:
                r = sessao.get(url, timeout=120)
                r.raise_for_status()
                p = r.json()["properties"]["parameter"]
                break
            except requests.RequestException:
                if i == 4:
                    raise
        d = pd.DataFrame(p)
        d = d[~d.index.str.endswith("13")]
        d.insert(0, "mes", d.index.str[4:].astype(int))
        d.insert(0, "ano", ano)
        d.insert(0, "cel_lon", lon)
        d.insert(0, "cel_lat", lat)
        return d

    with ThreadPoolExecutor(max_workers=4) as ex:
        df = pd.concat(list(ex.map(uma, celulas)), ignore_index=True)
    df[list(PARAMS)] = df[list(PARAMS)].mask(df[list(PARAMS)] <= -999)
    df = df.dropna(subset=list(PARAMS), how="all").rename(columns=PARAMS)   # meses ainda não consolidados
    colunas = ["cel_lat", "cel_lon", "ano", "mes", "umidade_solo_raiz", "chuva_mm_dia", "umidade_rel_pct",
               "temp_max_c", "temp_min_c", "vento_ms"]
    return df[colunas].sort_values(["cel_lat", "cel_lon", "mes"]).reset_index(drop=True)


def main() -> None:
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    print(f"1/2 clima mensal consolidado de {ano}")
    m = mensal(ano)
    m.to_csv(RAIZ / "data" / f"clima_mensal_{ano}.csv", index=False)
    print(f"  {len(m)} linhas, meses disponíveis: {sorted(m['mes'].unique())}")
    print("2/2 chuva diária dos últimos 120 dias")
    r = clima_app.atualizar_tudo()
    print("  ", r)


if __name__ == "__main__":
    main()
