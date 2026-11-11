"""Assistente do Safra Sentinela.

Não usa um modelo de linguagem: interpreta a pergunta (município, estado, cultura, safra e
intenção) e responde com números calculados na hora sobre a base de risco. Assim, toda resposta
pode ser conferida no painel e o assistente funciona sem internet e sem chave de API.

Cada resposta traz: texto, blocos visuais (cartões, tabelas, séries), sugestões de próxima
pergunta e o contexto da conversa, que o navegador devolve na mensagem seguinte.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app import clima, dados
from app.dados import NOME_CULTURA, NOME_UF, ROTULO_NIVEL, sem_acento
from app.mensagens import montar_mensagens

UF_POR_NOME = {sem_acento(nome): sigla for sigla, nome in NOME_UF.items()}
UF_POR_NOME.update({"minas": "MG", "rio grande norte": "RN"})
ANTES_DE_LUGAR = r"(?:em|de|do|da|para|pra|no|na|sobre|municipio|cidade)\s+"

ARTIGO = {"PB": "a", "BA": "a", "CE": "o", "PI": "o", "RN": "o", "MA": "o", "ES": "o"}  # demais: sem artigo


def em(uf: Optional[str]) -> str:
    """'na Paraíba', 'no Ceará', 'em Pernambuco', 'em todo o Semiárido'."""
    if not uf:
        return "em todo o Semiárido"
    art = ARTIGO.get(uf)
    return f"n{art} {NOME_UF[uf]}" if art else f"em {NOME_UF[uf]}"


def de(uf: Optional[str]) -> str:
    """'da Paraíba', 'do Ceará', 'de Pernambuco', 'do Semiárido'."""
    if not uf:
        return "do Semiárido"
    art = ARTIGO.get(uf)
    return f"d{art} {NOME_UF[uf]}" if art else f"de {NOME_UF[uf]}"


def negrito_lugar(frase: str) -> str:
    """Põe em negrito o nome do lugar, mantendo a preposição fora: 'na **Paraíba**'."""
    prep, _, nome = frase.partition(" ")
    return f"{prep} **{nome}**"


SUGESTOES_INICIAIS = [
    "Quais municípios têm maior risco na Paraíba?",
    "Qual o risco em Monteiro?",
    "Como está a chuva agora no Semiárido?",
    "Compare Ceará e Bahia",
    "Como funciona o modelo?",
]


def _real(valor: Optional[int]) -> str:
    return "A divulgar" if valor is None else ("Safra quebrou" if valor else "Safra normal")


def _data(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{round(v * 100)}%"


def _n(v: int) -> str:
    return f"{v:,}".replace(",", ".")


# ----------------------------------------------------------- leitura da pergunta
def _achar_ufs(original: str, norm: str) -> List[str]:
    achadas: List[Tuple[int, str]] = []
    for nome, sigla in UF_POR_NOME.items():
        pos = norm.find(nome)
        if pos >= 0 and re.search(rf"\b{re.escape(nome)}\b", norm):
            achadas.append((pos, sigla))
    # siglas só valem em maiúsculas ("PB"), para não confundir com "se", "pe", "ma"...
    for m in re.finditer(r"\b([A-Z]{2})\b", original):
        if m.group(1) in NOME_UF:
            achadas.append((m.start(), m.group(1)))
    vistas, ordem = set(), []
    for _, sigla in sorted(achadas):
        if sigla not in vistas:
            vistas.add(sigla)
            ordem.append(sigla)
    return ordem


def _achar_municipios(original: str, norm: str) -> List[Dict[str, Any]]:
    """Municípios citados na pergunta (o nome mais longo vence; homônimos voltam juntos)."""
    melhor_nome, achados = "", []
    for m in dados.municipios().values():
        chave = m["chave"]
        if len(chave) < 3 or len(chave) < len(melhor_nome) or chave not in norm:
            continue
        casou = re.search(rf"\b{re.escape(chave)}\b", norm)
        if not casou:
            continue
        if " " not in chave:
            # nome de uma palavra só ("Saúde", "Central"): exige contexto de lugar ou inicial maiúscula
            trecho = original[casou.start():casou.end()]
            tem_contexto = re.search(rf"{ANTES_DE_LUGAR}{re.escape(chave)}\b", norm)
            if not (tem_contexto or trecho[:1].isupper() or norm.strip(" ?!.") == chave):
                continue
        if len(chave) > len(melhor_nome):
            melhor_nome, achados = chave, [m]
        else:
            achados.append(m)
    return achados


def _entender(mensagem: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    norm = sem_acento(mensagem)
    e: Dict[str, Any] = {"norm": norm}
    ano = re.search(r"\b(20\d{2})\b", norm)
    e["ano"] = int(ano.group(1)) if ano else None
    e["cultura"] = "feijao" if "feij" in norm else ("milho" if "milho" in norm else None)
    e["ufs"] = _achar_ufs(mensagem, norm)
    e["municipios"] = _achar_municipios(mensagem, norm)
    # o nome de um estado dentro do nome de um município não conta como estado ("Belém do Piauí")
    if e["municipios"]:
        chave = e["municipios"][0]["chave"]
        e["ufs"] = [u for u in e["ufs"] if sem_acento(NOME_UF[u]) not in chave] or (
            [u for u in e["ufs"] if u in {m["uf"] for m in e["municipios"]}])

    def tem(*termos: str) -> bool:
        return any(t in norm for t in termos)

    if tem("agora", "hoje", "ultimos dias", "ultimas semanas", "recente", "tempo real", "esta chovendo",
           "dias sem chuva", "ultimos 30", "ultimos 90", "este mes"):
        e["intencao"] = "agora"
    elif tem("compar", " x ", " versus ", " vs ") and len(e["ufs"]) >= 2:
        e["intencao"] = "comparar"
    elif tem("mensagem", "sms", "whatsapp", "aviso para", "avisar"):
        e["intencao"] = "mensagem"
    elif tem("como funciona", "modelo", "acerta", "acerto", "precisao", "confiavel", "confianca",
             "machine", "algoritmo", "recall"):
        e["intencao"] = "modelo"
    elif tem("o que fazer", "que fazer", "orienta", "garantia", "seguro", "como agir"):
        e["intencao"] = "orientacao"
    elif tem("historico", "evolu", "ao longo", "ultimos anos", "todas as safras", "cada ano"):
        e["intencao"] = "historico"
    elif tem("choveu", "chuva", "seca", "estiagem") and not e["municipios"]:
        e["intencao"] = "chuva"
    elif tem("maior risco", "mais risco", "ranking", "top", "piores", "prioridade", "quais municipios",
             "quais cidades", "onde esta", "onde ha", "lista"):
        e["intencao"] = "ranking"
    elif tem("resumo", "panorama", "situacao", "como foi", "como esta", "visao geral", "quantos"):
        e["intencao"] = "resumo"
    elif tem("ajuda", "o que voce", "como usar", "o que posso") or norm.strip(" !?.") in (
            "oi", "ola", "bom dia", "boa tarde", "boa noite", "menu"):
        e["intencao"] = "ajuda"
    elif e["municipios"]:
        e["intencao"] = "municipio"
    elif e["ufs"]:
        e["intencao"] = "resumo"
    elif (e["ano"] or e["cultura"]) and ctx.get("intencao"):
        e["intencao"] = ctx["intencao"]  # continuação: "e o feijão?", "e em 2023?"
    else:
        e["intencao"] = None
    return e


# ------------------------------------------------------------------- respostas
def _resposta(texto: str, blocos=None, sugestoes=None, ctx=None, acoes=None) -> Dict[str, Any]:
    return {"texto": texto, "blocos": blocos or [], "sugestoes": sugestoes or [],
            "contexto": ctx or {}, "acoes": acoes or []}


def _acao_painel(ano: int, cultura: str, uf: Optional[str] = None, cod_mun: Optional[int] = None):
    params = {"ano": ano, "cultura": cultura, "uf": uf or "", "mun": cod_mun or ""}
    return {"rotulo": "Abrir no painel", "rota": "painel", "params": params}


def _tabela_municipios(linhas: List[Dict[str, Any]], com_chuva: bool = True) -> Dict[str, Any]:
    return {
        "tipo": "tabela",
        "colunas": ["Município", "Nível", "Chance de quebra", "Chuva (% do normal)", "Resultado real"],
        "linhas": [[f"{d['municipio']} ({d['uf']})", {"nivel": d["nivel"]}, _pct(d["prob"]),
                    "—" if d["chuva_pct"] is None else f"{d['chuva_pct']}%",
                    _real(d["quebra_real"])] for d in linhas],
        "perguntas": [f"Qual o risco em {d['municipio']} {d['uf']}?" for d in linhas],
    }


def _municipio(m: Dict[str, Any], ano: int, cultura: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    det = dados.detalhe_municipio(m["cod_mun"], ano, cultura)
    nome_cultura = NOME_CULTURA[cultura]
    if det is None:
        outra = "feijao" if cultura == "milho" else "milho"
        return _resposta(
            f"Não há previsão de {nome_cultura} para {m['municipio']} ({m['uf']}) em {ano}: o município "
            "não registrou plantio dessa cultura ou não tem histórico suficiente.",
            sugestoes=[f"E o {NOME_CULTURA[outra]} em {m['municipio']} {m['uf']}?",
                       f"Histórico de {m['municipio']} {m['uf']}"], ctx=ctx)
    if det["quebra_real"] is None:
        real = "Esta é a previsão atual: o resultado oficial do IBGE ainda não foi divulgado."
    else:
        real = f"No resultado oficial do IBGE, {'a safra quebrou' if det['quebra_real'] else 'a safra foi normal'}."
    chuva = "" if det["chuva_pct"] is None else f" A chuva da estação ficou em {det['chuva_pct']}% do normal."
    texto = (f"**{det['municipio']} ({det['uf']})**, {nome_cultura}, safra {ano}: "
             f"**{ROTULO_NIVEL[det['nivel']].lower()}**, com {_pct(det['prob'])} de chance de quebra.{chuva} "
             f"{real}")
    agora = clima.situacao(det["cod_mun"])
    if agora:
        texto += (f"\n\nChuva recente (até {_data(agora['dados_ate'])}): {round(agora['chuva_30d'])} mm nos "
                  f"últimos 30 dias e {agora['dias_sem_chuva']} dias seguidos sem chuva.")
    return _resposta(
        texto,
        blocos=[{"tipo": "municipio", "dados": det}],
        sugestoes=[f"Gerar mensagem para {det['municipio']} {det['uf']}",
                   f"Como está a chuva agora em {det['municipio']} {det['uf']}?",
                   f"Histórico de {det['municipio']} {det['uf']}"],
        ctx=ctx, acoes=[_acao_painel(ano, cultura, det["uf"], det["cod_mun"])])


def _historico(e, ano, cultura, ctx) -> Dict[str, Any]:
    nome_cultura = NOME_CULTURA[cultura]
    if e["municipios"]:
        m = e["municipios"][0]
        det = dados.detalhe_municipio(m["cod_mun"], ano, cultura)
        if det is None:
            return _municipio(m, ano, cultura, ctx)
        conferidas = [h for h in det["historico"] if h["quebra_real"] is not None]
        quebras = sum(h["quebra_real"] for h in conferidas)
        alertas = sum(1 for h in conferidas if h["nivel"] == "alto")
        texto = (f"Em **{det['municipio']} ({det['uf']})**, o {nome_cultura} quebrou em {quebras} das "
                 f"{len(conferidas)} safras entre {conferidas[0]['ano']} e {conferidas[-1]['ano']}. "
                 f"O modelo emitiu alerta em {alertas} delas.")
        atual = det["historico"][-1]
        if atual["quebra_real"] is None:
            texto += (f" Para {atual['ano']}, a previsão é de {ROTULO_NIVEL[atual['nivel']].lower()} "
                      f"({_pct(atual['prob'])}); o resultado ainda não saiu.")
        bloco = {"tipo": "serie", "titulo": "Chance de quebra estimada em cada safra",
                 "pontos": [{"rotulo": str(h["ano"]), "valor": round(h["prob"] * 100), "nivel": h["nivel"],
                             "marca": "quebrou" if h["quebra_real"] else ("previsão" if h["quebra_real"] is None else "")}
                            for h in det["historico"]]}
        return _resposta(texto, [bloco], [f"Qual o risco em {det['municipio']} {det['uf']}?",
                                          f"Gerar mensagem para {det['municipio']} {det['uf']}"], ctx,
                         [_acao_painel(ano, cultura, det["uf"], det["cod_mun"])])
    uf = e["ufs"][0] if e["ufs"] else None
    serie = dados.analises(cultura, uf)["historico"]
    pior = max(serie, key=lambda s: s["taxa"])
    texto = (f"Quebras de {nome_cultura} {negrito_lugar(em(uf))}, de {serie[0]['ano']} a {serie[-1]['ano']}. "
             f"O pior ano foi {pior['ano']}, com {round(pior['taxa'])}% das lavouras municipais em quebra.")
    bloco = {"tipo": "serie", "titulo": "Lavouras municipais com quebra (%)",
             "pontos": [{"rotulo": str(s["ano"])[2:], "valor": round(s["taxa"]),
                         "nivel": "alto" if s["taxa"] >= 30 else "baixo", "marca": ""} for s in serie]}
    return _resposta(texto, [bloco], ["Onde choveu menos em 2025?", f"Maior risco {em(uf)}"], ctx,
                     [{"rotulo": "Ver nas análises", "rota": "analises",
                       "params": {"cultura": cultura, "uf": uf or ""}}])


def _ranking(e, ano, cultura, ctx, por_chuva=False) -> Dict[str, Any]:
    uf = e["ufs"][0] if e["ufs"] else None
    linhas = dados.filtrar(ano, cultura, uf)
    nome_cultura = NOME_CULTURA[cultura]
    if not linhas:
        return _resposta(f"Não encontrei lavouras de {nome_cultura} {em(uf)} na safra {ano}.",
                         sugestoes=SUGESTOES_INICIAIS[:2], ctx=ctx)
    quantos = re.search(r"\b(?:top|os|as)\s+(\d{1,2})\b", e["norm"])
    n = max(3, min(int(quantos.group(1)), 15)) if quantos else 8
    if por_chuva:
        com_dado = [d for d in linhas if d["chuva_pct"] is not None]
        topo = sorted(com_dado, key=lambda d: d["chuva_pct"])[:n]
        r = dados.resumo(linhas)
        texto = (f"Onde menos choveu {negrito_lugar(em(uf))} na safra {ano} ({nome_cultura}). A média dos municípios "
                 f"ficou em {r['chuva_media_pct']}% do normal.")
    else:
        topo = sorted(linhas, key=lambda d: d["prob"], reverse=True)[:n]
        r = dados.resumo(linhas)
        texto = (f"Os {len(topo)} municípios de maior risco para {nome_cultura} {negrito_lugar(em(uf))}, safra {ano}. "
                 f"Ao todo, {_n(r['alto'])} de {_n(r['safras'])} municípios estão em risco alto.")
    outra = "feijão" if cultura == "milho" else "milho"
    return _resposta(texto, [_tabela_municipios(topo)],
                     [f"E o {outra}?", f"Resumo {de(uf)} em {ano}", f"Onde choveu menos {em(uf)}?" if not por_chuva
                      else f"Maior risco {em(uf)}"],
                     ctx, [_acao_painel(ano, cultura, uf)])


def _resumo(e, ano, cultura, ctx) -> Dict[str, Any]:
    uf = e["ufs"][0] if e["ufs"] else None
    linhas = dados.filtrar(ano, cultura, uf)
    onde = NOME_UF[uf] if uf else "Semiárido"
    if not linhas:
        return _resposta(f"Não há dados de {NOME_CULTURA[cultura]} para {onde} em {ano}.",
                         sugestoes=SUGESTOES_INICIAIS[:2], ctx=ctx)
    r = dados.resumo(linhas)
    texto = (f"**{onde}**, {NOME_CULTURA[cultura]}, safra {ano}: {_n(r['alto'])} municípios em risco alto e "
             f"{_n(r['atencao'])} em atenção, de {_n(r['safras'])} com plantio. ")
    itens = [
        {"rotulo": "Risco alto", "valor": _n(r["alto"]), "detalhe": _pct(r["alto"] / r["safras"]) + " dos municípios"},
        {"rotulo": "Em atenção", "valor": _n(r["atencao"]), "detalhe": "risco acima do normal"},
        {"rotulo": "Chuva da estação", "valor": "—" if r["chuva_media_pct"] is None else f"{r['chuva_media_pct']}%",
         "detalhe": "do normal, em média"},
    ]
    if r["conferidas"]:
        texto += f"Das {_n(r['quebras_reais'])} quebras confirmadas, o modelo avisou {_n(r['quebras_avisadas'])}."
        itens += [
            {"rotulo": "Quebras avisadas", "valor": _pct(r["recall"]), "detalhe": f"{_n(r['quebras_avisadas'])} de {_n(r['quebras_reais'])}"},
            {"rotulo": "Alertas confirmados", "valor": _pct(r["precisao"]), "detalhe": f"{_n(r['alertas_confirmados'])} de {_n(r['alertas_conferidos'])}"},
        ]
    else:
        texto += "É a previsão atual: o resultado oficial do IBGE ainda não foi divulgado."
    bloco = {"tipo": "kpis", "itens": itens}
    return _resposta(texto, [bloco], [f"Maior risco {em(uf)}", f"Histórico {de(uf)}", "E o feijão?"
                                      if cultura == "milho" else "E o milho?"],
                     ctx, [_acao_painel(ano, cultura, uf)])


def _comparar(e, ano, cultura, ctx) -> Dict[str, Any]:
    linhas = []
    for uf in e["ufs"][:4]:
        r = dados.resumo(dados.filtrar(ano, cultura, uf))
        if not r["safras"]:
            continue
        linhas.append([NOME_UF[uf], _n(r["safras"]),
                       _pct(r["quebras_reais"] / r["conferidas"]) if r["conferidas"] else "A divulgar",
                       _pct(r["alto"] / r["safras"]), _pct(r["recall"]), _pct(r["precisao"])])
    nomes = " e ".join(NOME_UF[u] for u in e["ufs"][:4])
    texto = (f"Comparação entre **{nomes}**, {NOME_CULTURA[cultura]}, safra {ano}. “Quebras avisadas” é a "
             "parte das perdas reais que recebeu alerta; “alertas confirmados” é a parte dos alertas que "
             "virou perda.")
    bloco = {"tipo": "tabela",
             "colunas": ["Estado", "Municípios", "Safras que quebraram", "Em risco alto", "Quebras avisadas",
                         "Alertas confirmados"], "linhas": linhas}
    return _resposta(texto, [bloco], [f"Maior risco {em(e['ufs'][0])}", "Como funciona o modelo?"], ctx,
                     [{"rotulo": "Ver nas análises", "rota": "analises", "params": {"cultura": cultura}}])


def _mensagem(e, ano, cultura, ctx) -> Dict[str, Any]:
    m = e["municipios"][0] if e["municipios"] else dados.municipios().get(ctx.get("cod_mun") or 0)
    if not m:
        return _resposta("Para qual município você quer o aviso? Escreva, por exemplo: "
                         "“Gerar mensagem para Monteiro PB”.",
                         sugestoes=["Gerar mensagem para Monteiro PB", "Gerar mensagem para Paulistana PI"], ctx=ctx)
    linha = next(iter(dados.filtrar(ano, cultura, cod_mun=m["cod_mun"])), None)
    if not linha:
        return _municipio(m, ano, cultura, ctx)
    msgs = montar_mensagens(linha)
    texto = (f"Este é o aviso que o agricultor de **{linha['municipio']} ({linha['uf']})** receberia para "
             f"{NOME_CULTURA[cultura]} na safra {ano} ({ROTULO_NIVEL[linha['nivel']].lower()}).")
    return _resposta(texto, [{"tipo": "mensagem", **msgs}],
                     [f"Qual o risco em {linha['municipio']} {linha['uf']}?", "O que fazer em risco alto?"], ctx,
                     [{"rotulo": "Abrir no gerador de avisos", "rota": "utilidades",
                       "params": {"mun": linha["cod_mun"], "cultura": cultura, "ano": ano}}])


CLASSE_CHUVA = {"muito_abaixo": "muito abaixo do normal", "abaixo": "abaixo do normal", "normal": "dentro do normal",
                "acima": "acima do normal", "seca": "época normalmente seca"}


def _agora(e, ctx) -> Dict[str, Any]:
    """Chuva recente, quase em tempo real (NASA POWER diário)."""
    if e["municipios"]:
        m = e["municipios"][0]
        s = clima.situacao(m["cod_mun"])
        if not s:
            return _resposta("Ainda não há dados de chuva recente carregados. Abra o painel e use “Atualizar chuva”.", ctx=ctx)
        comparacao = (f"{s['pct_90d']}% do normal para o período" if s["pct_90d"] is not None
                      else "numa época em que normalmente quase não chove")
        texto = (f"Chuva em **{m['municipio']} ({m['uf']})** até {_data(s['dados_ate'])}: {round(s['chuva_90d'])} mm "
                 f"nos últimos 90 dias, {comparacao}. São {s['dias_sem_chuva']} dias seguidos sem chuva.")
        bloco = {"tipo": "kpis", "itens": [
            {"rotulo": "Últimos 30 dias", "valor": f"{round(s['chuva_30d'])} mm", "detalhe": f"normal: {round(s['normal_30d'])} mm"},
            {"rotulo": "Últimos 90 dias", "valor": f"{round(s['chuva_90d'])} mm", "detalhe": f"normal: {round(s['normal_90d'])} mm"},
            {"rotulo": "Dias sem chuva", "valor": str(s["dias_sem_chuva"]), "detalhe": "seguidos, até a última medição"},
        ]}
        return _resposta(texto, [bloco], [f"Qual o risco em {m['municipio']} {m['uf']}?", "Como está a chuva agora no Semiárido?"],
                         ctx, [{"rotulo": "Abrir no painel", "rota": "painel", "params": {"mun": m["cod_mun"], "modo": "chuva"}}])
    uf = e["ufs"][0] if e["ufs"] else None
    todos = [(m, clima.situacao(c)) for c, m in dados.municipios().items() if not uf or m["uf"] == uf]
    todos = [(m, s) for m, s in todos if s]
    if not todos:
        return _resposta("Ainda não há dados de chuva recente carregados. Abra o painel e use “Atualizar chuva”.", ctx=ctx)
    contagem: Dict[str, int] = {}
    for _, s in todos:
        contagem[s["classe_90d"]] = contagem.get(s["classe_90d"], 0) + 1
    ate = max(s["dados_ate"] for _, s in todos)
    chovendo = [(m, s) for m, s in todos if s["classe_90d"] != "seca"]
    texto = (f"Chuva dos últimos 90 dias {negrito_lugar(em(uf))}, com dados até {_data(ate)}. "
             f"{_n(contagem.get('seca', 0))} dos {_n(len(todos))} municípios estão na época normalmente seca. ")
    if chovendo:
        abaixo = contagem.get("muito_abaixo", 0) + contagem.get("abaixo", 0)
        texto += (f"Entre os {_n(len(chovendo))} em que já deveria chover, {_n(abaixo)} estão abaixo do normal.")
    piores = sorted(chovendo, key=lambda par: par[1]["pct_90d"])[:8]
    blocos = [{"tipo": "kpis", "itens": [
        {"rotulo": "Muito abaixo do normal", "valor": _n(contagem.get("muito_abaixo", 0)), "detalhe": "menos de 50%"},
        {"rotulo": "Abaixo", "valor": _n(contagem.get("abaixo", 0)), "detalhe": "50% a 80%"},
        {"rotulo": "Dentro do normal", "valor": _n(contagem.get("normal", 0)), "detalhe": "80% a 120%"},
        {"rotulo": "Acima", "valor": _n(contagem.get("acima", 0)), "detalhe": "mais de 120%"},
    ]}]
    if piores:
        blocos.append({"tipo": "tabela",
                       "colunas": ["Município", "Chuva em 90 dias", "Normal do período", "% do normal", "Dias sem chuva"],
                       "linhas": [[f"{m['municipio']} ({m['uf']})", f"{round(s['chuva_90d'])} mm", f"{round(s['normal_90d'])} mm",
                                   f"{s['pct_90d']}%", str(s["dias_sem_chuva"])] for m, s in piores],
                       "perguntas": [f"Como está a chuva agora em {m['municipio']} {m['uf']}?" for m, _ in piores]})
    return _resposta(texto, blocos, ["Qual o risco em Monteiro?", f"Maior risco {em(uf)}"], ctx,
                     [{"rotulo": "Ver o mapa da chuva", "rota": "painel", "params": {"modo": "chuva", "uf": uf or ""}}])


def _modelo(ctx) -> Dict[str, Any]:
    r = dados.resumo(dados.previsoes())
    texto = ("O Safra Sentinela usa um modelo de **Gradient Boosting** treinado com as safras de 2003 a 2019. "
             "Ele cruza o clima medido por satélite (chuva, temperatura, umidade do solo) com o histórico de "
             "cada município e estima a chance de o rendimento ficar abaixo da metade do habitual.\n\n"
             f"Nas safras de 2020 a 2025, que o modelo nunca viu, ele avisou **{_pct(r['recall'])} das quebras** "
             f"e **{_pct(r['precisao'])} dos alertas se confirmaram**. Por isso o aviso fala em risco, e não em "
             "certeza. A chance de quebra mostrada é uma probabilidade calibrada: o alerta sai a partir de "
             f"{_pct(dados.limiar_alerta())} nas safras conferidas, porque a quebra é um evento raro. O acerto varia entre estados: é menor no Ceará e maior na Bahia e na Paraíba.\n\n"
             f"Para a safra de {dados.anos()[0]}, o mesmo modelo foi reajustado com todas as safras conhecidas "
             "(2003 a 2025) e usa o clima consolidado da NASA. O resultado oficial ainda não saiu, então essa "
             "previsão não pode ser conferida por enquanto.")
    bloco = {"tipo": "kpis", "itens": [
        {"rotulo": "Quebras avisadas", "valor": _pct(r["recall"]), "detalhe": f"{_n(r['quebras_avisadas'])} de {_n(r['quebras_reais'])}"},
        {"rotulo": "Alertas confirmados", "valor": _pct(r["precisao"]), "detalhe": f"{_n(r['alertas_confirmados'])} de {_n(r['alertas_conferidos'])}"},
        {"rotulo": "Safras avaliadas", "valor": _n(r["conferidas"]), "detalhe": "2020 a 2025"},
    ]}
    return _resposta(texto, [bloco], ["Compare Ceará e Bahia", "O que fazer em risco alto?"], ctx,
                     [{"rotulo": "Testar outro limiar nas análises", "rota": "analises", "params": {}}])


def _orientacao(ctx) -> Dict[str, Any]:
    texto = ("Quando o município entra em **risco alto**, a recomendação ao agricultor é:\n\n"
             "1. Guardar semente e alimento antes de vender a produção.\n"
             "2. Procurar o técnico de extensão ou o sindicato para avaliar a lavoura.\n"
             "3. Conferir se a inscrição no Garantia-Safra está em dia.\n\n"
             "O Garantia-Safra é um benefício federal para agricultores familiares do Semiárido que perdem "
             "pelo menos metade da produção por seca ou excesso de chuva. As regras e os prazos de adesão "
             "devem ser confirmados na prefeitura ou no sindicato.")
    return _resposta(texto, sugestoes=["Gerar mensagem para Monteiro PB", "Como funciona o modelo?"], ctx=ctx)


def _ajuda(ctx) -> Dict[str, Any]:
    texto = ("Sou o assistente do Safra Sentinela. Respondo com os números da base de risco, sobre:\n\n"
             "- o **risco de um município** (“Qual o risco em Monteiro?”)\n"
             "- os **municípios de maior risco** de um estado\n"
             "- o **resumo** ou a **comparação** entre estados\n"
             "- o **histórico** de quebras e a **chuva de agora**, quase em tempo real\n"
             "- o **aviso** que o agricultor recebe e **como o modelo funciona**\n\n"
             f"Você pode indicar a cultura (milho ou feijão) e a safra ({dados.anos()[-1]} a {dados.anos()[0]}).")
    return _resposta(texto, sugestoes=SUGESTOES_INICIAIS, ctx=ctx)


def responder(mensagem: str, contexto: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ctx = dict(contexto or {})
    mensagem = (mensagem or "").strip()[:400]
    if not mensagem:
        return _ajuda(ctx)
    e = _entender(mensagem, ctx)

    anos = dados.anos()
    ano = e["ano"] or ctx.get("ano") or anos[0]
    if ano not in anos:
        return _resposta(f"Tenho previsões para as safras de {anos[-1]} a {anos[0]}. Para anos anteriores, "
                         "posso mostrar o histórico de quebras.",
                         sugestoes=["Histórico do Semiárido", f"Resumo de {anos[0]}"], ctx=ctx)
    cultura = e["cultura"] or ctx.get("cultura") or "milho"

    # homônimos: usa o estado citado; se não houver, pergunta
    if e["municipios"] and len(e["municipios"]) > 1:
        do_estado = [m for m in e["municipios"] if m["uf"] in e["ufs"]]
        if len(do_estado) == 1:
            e["municipios"] = do_estado
        else:
            nome = e["municipios"][0]["municipio"]
            return _resposta(f"Há mais de um município chamado {nome}. Qual deles?",
                             sugestoes=[f"{m['municipio']} {m['uf']}" for m in e["municipios"][:6]], ctx=ctx)
    if e["municipios"]:
        e["ufs"] = [u for u in e["ufs"] if u != e["municipios"][0]["uf"]] if e["intencao"] == "comparar" else e["ufs"]

    intencao = e["intencao"]
    # continuação da conversa: reaproveita o lugar da pergunta anterior
    if intencao in ("municipio", "historico", "mensagem", "agora") and not e["municipios"] and ctx.get("cod_mun") \
            and not e["ufs"] and "semiarido" not in e["norm"]:
        m = dados.municipios().get(ctx["cod_mun"])
        if m:
            e["municipios"] = [m]
    if intencao in ("ranking", "resumo", "chuva", "historico") and not e["ufs"] and not e["municipios"] \
            and ctx.get("uf") and "semiarido" not in e["norm"]:
        e["ufs"] = [ctx["uf"]]

    novo = {"ano": ano, "cultura": cultura, "intencao": intencao,
            "uf": e["ufs"][0] if e["ufs"] else (e["municipios"][0]["uf"] if e["municipios"] else None),
            "cod_mun": e["municipios"][0]["cod_mun"] if e["municipios"] else None}

    if intencao == "municipio" and e["municipios"]:
        return _municipio(e["municipios"][0], ano, cultura, novo)
    if intencao == "agora":
        return _agora(e, novo)
    if intencao == "historico":
        return _historico(e, ano, cultura, novo)
    if intencao == "mensagem":
        return _mensagem(e, ano, cultura, novo)
    if intencao == "ranking":
        return _ranking(e, ano, cultura, novo)
    if intencao == "chuva":
        return _ranking(e, ano, cultura, novo, por_chuva=True)
    if intencao == "comparar":
        return _comparar(e, ano, cultura, novo)
    if intencao == "resumo":
        return _resumo(e, ano, cultura, novo)
    if intencao == "modelo":
        return _modelo(novo)
    if intencao == "orientacao":
        return _orientacao(novo)
    if intencao == "ajuda":
        return _ajuda(novo)

    return _resposta("Não entendi a pergunta. Tente citar um município ou um estado do Semiárido, ou escolha "
                     "uma das sugestões abaixo.", sugestoes=SUGESTOES_INICIAIS, ctx=ctx)
