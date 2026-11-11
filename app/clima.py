"""Chuva recente, quase em tempo real (NASA POWER, dados diários).

A NASA publica a chuva diária com cerca de três dias de atraso. Este módulo:
  - baixa os últimos dias para as 331 células de clima do Semiárido e guarda em app/data;
  - resume a situação de cada município (30 e 90 dias, comparação com o normal, dias sem chuva);
  - pode se atualizar sozinho, em segundo plano, enquanto o servidor roda.

Só usa a biblioteca padrão, para o servidor continuar leve.
Os dias mais recentes são preliminares: a NASA os revisa nos meses seguintes.
"""
from __future__ import annotations

import calendar
import csv
import json
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app import dados

ARQUIVO = dados.PASTA / "chuva_diaria.csv"
META = dados.PASTA / "chuva_diaria.json"
DIAS_GUARDADOS = 120
DIA_SEM_CHUVA_MM = 1.0          # abaixo disso o dia conta como seco
NORMAL_MINIMO_MM_DIA = 0.55      # normal abaixo disso (≈50 mm em 90 dias) é "época seca": não se compara com o normal
URL = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR&community=AG"
       "&longitude={lon}&latitude={lat}&start={ini}&end={fim}&format=JSON")

Celula = Tuple[float, float]
_trava = threading.Lock()
_cache: Dict[str, Any] = {"series": None, "meta": None}
estado = {"atualizando": False, "feitas": 0, "total": 0, "erro": None}


def baixar_celula(celula: Celula, inicio: date, fim: date, tentativas: int = 4) -> Dict[str, float]:
    """Chuva diária (mm) de uma célula: {'AAAA-MM-DD': mm}. Dias ainda não publicados ficam de fora."""
    lat, lon = celula
    url = URL.format(lat=lat, lon=lon, ini=inicio.strftime("%Y%m%d"), fim=fim.strftime("%Y%m%d"))
    for i in range(tentativas):
        try:
            pedido = urllib.request.Request(url, headers={"User-Agent": "safra-sentinela/1.0"})
            with urllib.request.urlopen(pedido, timeout=90) as r:
                bruto = json.load(r)["properties"]["parameter"]["PRECTOTCORR"]
            return {f"{k[:4]}-{k[4:6]}-{k[6:]}": float(v) for k, v in bruto.items() if float(v) > -900}
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))
    return {}


def celulas() -> List[Celula]:
    return sorted({m["celula"] for m in dados.municipios().values()})


def atualizar_tudo(trabalhadores: int = 6) -> Dict[str, Any]:
    """Baixa os últimos DIAS_GUARDADOS dias de todas as células e regrava o arquivo de uma vez."""
    if not _trava.acquire(blocking=False):
        return {"ok": False, "motivo": "Já existe uma atualização em andamento."}
    try:
        todas = celulas()
        estado.update(atualizando=True, feitas=0, total=len(todas), erro=None)
        fim = date.today()
        inicio = fim - timedelta(days=DIAS_GUARDADOS + 5)

        def uma(c: Celula):
            serie = baixar_celula(c, inicio, fim)
            estado["feitas"] += 1
            return c, serie

        with ThreadPoolExecutor(max_workers=trabalhadores) as ex:
            resultados = list(ex.map(uma, todas))

        ultimo = max((max(s) for _, s in resultados if s), default=None)
        temporario = ARQUIVO.with_suffix(".tmp")
        with open(temporario, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["cel_lat", "cel_lon", "data", "chuva_mm"])
            for (lat, lon), serie in resultados:
                for dia in sorted(serie):
                    w.writerow([lat, lon, dia, round(serie[dia], 2)])
        temporario.replace(ARQUIVO)
        meta = {"atualizado_em": datetime.now().isoformat(timespec="seconds"), "dados_ate": ultimo,
                "celulas": len(todas), "fonte": "NASA POWER (diário, preliminar)"}
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        _cache.update(series=None, meta=None)
        return {"ok": True, **meta}
    except Exception as e:  # rede fora do ar, NASA indisponível etc.: mantém os dados anteriores
        estado["erro"] = f"Não foi possível falar com a NASA POWER ({type(e).__name__})."
        return {"ok": False, "motivo": estado["erro"]}
    finally:
        estado["atualizando"] = False
        _trava.release()


def atualizar_em_segundo_plano() -> bool:
    if estado["atualizando"]:
        return False
    threading.Thread(target=atualizar_tudo, daemon=True, name="atualizar-chuva").start()
    return True


def meta() -> Optional[Dict[str, Any]]:
    if _cache["meta"] is None and META.exists():
        _cache["meta"] = json.loads(META.read_text(encoding="utf-8"))
    return _cache["meta"]


def horas_desde_atualizacao() -> Optional[float]:
    m = meta()
    if not m:
        return None
    return (datetime.now() - datetime.fromisoformat(m["atualizado_em"])).total_seconds() / 3600


def atualizar_se_velho() -> None:
    """Chamado na subida do servidor: renova os dados se passaram mais de SAFRA_ATUALIZAR_HORAS (padrão 12)."""
    limite = float(os.getenv("SAFRA_ATUALIZAR_HORAS", "12"))
    if limite <= 0:
        return
    horas = horas_desde_atualizacao()
    if horas is None or horas > limite:
        atualizar_em_segundo_plano()


def _series() -> Dict[Celula, List[Tuple[date, float]]]:
    if _cache["series"] is None:
        series: Dict[Celula, List[Tuple[date, float]]] = {}
        if ARQUIVO.exists():
            with open(ARQUIVO, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    chave = (float(r["cel_lat"]), float(r["cel_lon"]))
                    series.setdefault(chave, []).append((date.fromisoformat(r["data"]), float(r["chuva_mm"])))
        _cache["series"] = series
    return _cache["series"]


def _normal(normais: List[float], inicio: date, fim: date) -> float:
    """Chuva normal (mm) entre duas datas, rateando o normal de cada mês pelos dias da janela."""
    total, dia = 0.0, inicio
    while dia <= fim:
        total += (normais[dia.month - 1] or 0) / calendar.monthrange(dia.year, dia.month)[1]
        dia += timedelta(days=1)
    return total


def _classe(pct: Optional[float]) -> str:
    if pct is None:
        return "seca"            # época normalmente seca
    if pct < 50:
        return "muito_abaixo"
    if pct < 80:
        return "abaixo"
    if pct <= 120:
        return "normal"
    return "acima"


def situacao(cod_mun: int, com_serie: bool = False) -> Optional[Dict[str, Any]]:
    m = dados.municipios().get(cod_mun)
    serie = _series().get(m["celula"]) if m else None
    if not serie:
        return None
    ultimo = serie[-1][0]
    saida: Dict[str, Any] = {"cod_mun": cod_mun, "dados_ate": ultimo.isoformat()}
    for dias in (30, 90):
        inicio = ultimo - timedelta(days=dias - 1)
        chuva = sum(mm for d, mm in serie if d >= inicio)
        normal = _normal(m["chuva_normal"], inicio, ultimo)
        pct = round(100 * chuva / normal) if normal >= NORMAL_MINIMO_MM_DIA * dias else None
        saida[f"chuva_{dias}d"] = round(chuva, 1)
        saida[f"normal_{dias}d"] = round(normal, 1)
        saida[f"pct_{dias}d"] = pct
        saida[f"classe_{dias}d"] = _classe(pct)
    secos = 0
    for _, mm in reversed(serie):
        if mm >= DIA_SEM_CHUVA_MM:
            break
        secos += 1
    saida["dias_sem_chuva"] = secos
    saida["dias_sem_chuva_no_limite"] = secos >= len(serie)   # seca mais longa que a janela guardada
    if com_serie:
        saida["serie"] = [{"data": d.isoformat(), "mm": mm} for d, mm in serie[-90:]]
    return saida


def mapa() -> Dict[str, Any]:
    """Situação resumida de todos os municípios, para colorir o mapa."""
    itens = {}
    for cod in dados.municipios():
        s = situacao(cod)
        if s:
            itens[cod] = {k: s[k] for k in ("chuva_90d", "normal_90d", "pct_90d", "classe_90d",
                                             "chuva_30d", "dias_sem_chuva")}
    return {"meta": meta(), "municipios": itens}
