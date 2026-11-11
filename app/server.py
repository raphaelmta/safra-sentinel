"""Safra Sentinela — servidor da plataforma web (API + arquivos estáticos).

Uso:  uvicorn app.server:app --port 8000      (ou ./run.sh)
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import auth, chat, clima, dados
from app.mensagens import montar_mensagens

WEB = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Safra Sentinela", version="1.0.0", docs_url="/api/docs", redoc_url=None)


# ----------------------------------------------------------------------- sessão
class Credenciais(BaseModel):
    email: str = Field(max_length=200)
    senha: str = Field(max_length=200)


class Pergunta(BaseModel):
    mensagem: str = Field(max_length=400)
    contexto: Dict[str, Any] = {}


def usuario_atual(safra_sessao: Optional[str] = Cookie(default=None)) -> Dict[str, Any]:
    usuario = auth.ler_token(safra_sessao)
    if not usuario:
        raise HTTPException(status_code=401, detail="Sessão expirada. Entre novamente.")
    return usuario


def _abrir_sessao(resposta: Response, usuario: Dict[str, str]) -> Dict[str, str]:
    resposta.set_cookie(auth.COOKIE, auth.criar_token(usuario), max_age=auth.DURACAO,
                        httponly=True, samesite="lax")
    return usuario


@app.post("/api/login")
def login(credenciais: Credenciais, resposta: Response):
    usuario = auth.verificar(credenciais.email, credenciais.senha)
    if not usuario:
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    return _abrir_sessao(resposta, usuario)


@app.post("/api/login/visitante")
def login_visitante(resposta: Response):
    """Acesso de demonstração, sem senha, para quem vai avaliar o projeto."""
    return _abrir_sessao(resposta, dict(auth.VISITANTE))


@app.post("/api/logout")
def logout(resposta: Response):
    resposta.delete_cookie(auth.COOKIE)
    return {"ok": True}


@app.get("/api/eu")
def eu(usuario: Dict[str, Any] = Depends(usuario_atual)):
    return usuario


# ------------------------------------------------------------------- público
@app.get("/api/publico/pontos")
def pontos_publicos():
    """Pontos do mapa da tela de entrada (dados públicos agregados, sem login)."""
    ano = dados.anos()[0]
    linhas = dados.filtrar(ano, "milho")
    r = dados.resumo(linhas)
    return {"ano": ano, "municipios": r["safras"], "alto": r["alto"],
            "pontos": [[d["lon"], d["lat"], d["nivel"][0]] for d in linhas]}


# ---------------------------------------------------------------------- dados
@app.get("/api/opcoes", dependencies=[Depends(usuario_atual)])
def opcoes():
    return {
        "anos": dados.anos(),
        "culturas": [{"id": c, "nome": dados.NOME_CULTURA[c].capitalize()} for c in dados.culturas()],
        "ufs": [{"id": u, "nome": dados.NOME_UF.get(u, u)} for u in dados.ufs()],
        "limiar_modelo": dados.limiar_alerta(),
        "limiares": dados.limiares(),
        "anos_sem_resultado": dados.anos_sem_resultado(),
    }


@app.get("/api/risco", dependencies=[Depends(usuario_atual)])
def risco(ano: int, cultura: str = "milho", uf: Optional[str] = None):
    linhas = sorted(dados.filtrar(ano, cultura, uf or None), key=lambda d: d["prob"], reverse=True)
    campos = ("cod_mun", "municipio", "uf", "lat", "lon", "prob", "nivel", "chuva_pct", "quebra_real")
    return {"ano": ano, "cultura": cultura, "uf": uf or None, "resumo": dados.resumo(linhas),
            "municipios": [{k: d[k] for k in campos} for d in linhas]}


@app.get("/api/municipio/{cod_mun}", dependencies=[Depends(usuario_atual)])
def municipio(cod_mun: int, ano: int, cultura: str = "milho"):
    det = dados.detalhe_municipio(cod_mun, ano, cultura)
    if det is None:
        raise HTTPException(status_code=404, detail="Sem previsão para este município, safra e cultura.")
    det["mensagens"] = montar_mensagens(det)
    det["chuva_recente"] = clima.situacao(cod_mun, com_serie=True)
    return det


# -------------------------------------------------------------- chuva recente
@app.on_event("startup")
def _renovar_chuva():
    clima.atualizar_se_velho()


@app.get("/api/clima/mapa", dependencies=[Depends(usuario_atual)])
def clima_mapa():
    return clima.mapa()


@app.get("/api/clima/status", dependencies=[Depends(usuario_atual)])
def clima_status():
    return {"meta": clima.meta(), **clima.estado}


@app.post("/api/clima/atualizar", dependencies=[Depends(usuario_atual)])
def clima_atualizar():
    """Busca na NASA os dias mais recentes (leva cerca de um minuto, em segundo plano)."""
    horas = clima.horas_desde_atualizacao()
    if horas is not None and horas < 1 and not clima.estado["atualizando"]:
        return {"iniciada": False, "motivo": "Os dados foram atualizados há menos de uma hora.",
                "meta": clima.meta(), **clima.estado}
    iniciada = clima.atualizar_em_segundo_plano()
    return {"iniciada": iniciada, "meta": clima.meta(), **clima.estado}


@app.get("/api/municipios", dependencies=[Depends(usuario_atual)])
def buscar_municipios(q: str = ""):
    return dados.buscar_municipios(q)


@app.get("/api/analises", dependencies=[Depends(usuario_atual)])
def analises(cultura: Optional[str] = None, uf: Optional[str] = None):
    return dados.analises(cultura or None, uf or None)


@app.post("/api/chat", dependencies=[Depends(usuario_atual)])
def conversar(pergunta: Pergunta):
    return chat.responder(pergunta.mensagem, pergunta.contexto)


@app.get("/api/chat/sugestoes", dependencies=[Depends(usuario_atual)])
def sugestoes():
    return chat.SUGESTOES_INICIAIS


@app.get("/api/exportar.csv", dependencies=[Depends(usuario_atual)])
def exportar(ano: int, cultura: str = "milho", uf: Optional[str] = None):
    linhas = sorted(dados.filtrar(ano, cultura, uf or None), key=lambda d: d["prob"], reverse=True)
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(["cod_ibge", "municipio", "uf", "safra", "cultura", "nivel", "chance_quebra_pct",
                "chuva_pct_normal", "resultado_real"])
    for d in linhas:
        w.writerow([d["cod_mun"], d["municipio"], d["uf"], d["ano"], dados.NOME_CULTURA[d["cultura"]],
                    dados.ROTULO_NIVEL[d["nivel"]], round(d["prob"] * 100),
                    "" if d["chuva_pct"] is None else d["chuva_pct"],
                    "a divulgar" if d["quebra_real"] is None else ("quebrou" if d["quebra_real"] else "normal")])
    nome = f"safra_sentinela_{cultura}_{ano}{'_' + uf if uf else ''}.csv"
    # BOM para o Excel abrir os acentos corretamente
    return StreamingResponse(iter(["﻿" + saida.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{nome}"'})


# ------------------------------------------------------------------- frontend
@app.middleware("http")
async def sem_cache_no_desenvolvimento(request, call_next):
    resposta = await call_next(request)
    if request.url.path.endswith((".js", ".css", ".html")) or request.url.path == "/":
        resposta.headers["Cache-Control"] = "no-cache"
    return resposta


@app.get("/")
def inicio():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=str(WEB)), name="web")
