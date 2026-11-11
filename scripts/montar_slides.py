"""Monta a proposta executiva (pitch) do Safra Sentinela em PPTX.

Uso: python scripts/montar_slides.py
Saída: pitch/GS_2TSCOA_Pitch_SafraSentinela_RHEAL.pptx

Os números vêm das tabelas do projeto (data/ e notebook/), não são digitados à mão,
exceto os resultados do modelo, que repetem a tabela final do notebook.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app import dados as dados_app          # noqa: E402
from app.mensagens import montar_mensagens  # noqa: E402

SAIDA = RAIZ / "pitch" / "GS_2TSCOA_Pitch_SafraSentinela_RHEAL.pptx"
PROT = RAIZ / "prototipo" / "slides"

# ----------------------------------------------------------------- identidade
VERDE_ESC, VERDE, VERDE_CLARO = "16291F", "2F6B4F", "DCEBE2"
AMBAR, VERMELHO, CINZA_PONTO = "E3A21A", "D9483B", "8A968F"
TINTA, TINTA2, FUNDO, BRANCO = "1D2420", "56635C", "F2F5F3", "FFFFFF"
FONTE = "Calibri"

EQUIPE = [  # ordem alfabética
    ("Arthur Evangelista Thomazini", "RM562260", False),
    ("Elom Eduardo Maio Nascimento", "RM564921", False),
    ("Henrique Soares Meira", "RM565646", False),
    ("Luiz Phelipe Silva Menezes Araujo", "RM566417", True),   # aluno responsável
    ("Raphael Martins Teixeira Amaral", "RM562664", False),
]
LINK_VIDEO = "[inserir aqui o link público do YouTube]"

# Resultados do notebook (seção 6, conjunto de teste 2020–2025)
MODELOS = {"Regra da chuva (sem ML)": (0.58, 0.20), "Regressão Logística": (0.55, 0.32),
           "Random Forest": (0.65, 0.27), "Gradient Boosting": (0.60, 0.31)}


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
EM_BRANCO = prs.slide_layouts[6]


# ------------------------------------------------------------------- helpers
def novo(fundo=BRANCO, notas=""):
    s = prs.slides.add_slide(EM_BRANCO)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(fundo)
    if notas:
        s.notes_slide.notes_text_frame.text = notas
    return s


def texto(s, x, y, w, h, conteudo, tam=15, cor=TINTA, negrito=False, alinh=PP_ALIGN.LEFT,
          ancora=MSO_ANCHOR.TOP, italico=False, espaco=4, nome=None):
    """conteudo: str, ou lista de parágrafos; cada parágrafo é str ou lista de (texto, {opções})."""
    cx = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if nome:
        cx.name = nome
    tf = cx.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancora
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    paragrafos = conteudo if isinstance(conteudo, list) else [conteudo]
    for i, par in enumerate(paragrafos):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = alinh
        p.space_after = Pt(espaco)
        for trecho in (par if isinstance(par, list) else [(par, {})]):
            t, o = trecho if isinstance(trecho, tuple) else (trecho, {})
            r = p.add_run()
            r.text = t
            f = r.font
            f.name, f.size = FONTE, Pt(o.get("tam", tam))
            f.bold, f.italic = o.get("negrito", negrito), o.get("italico", italico)
            f.color.rgb = rgb(o.get("cor", cor))
    return cx


def forma(s, tipo, x, y, w, h, cor, linha=None, nome=None):
    f = s.shapes.add_shape(tipo, Inches(x), Inches(y), Inches(w), Inches(h))
    f.fill.solid()
    f.fill.fore_color.rgb = rgb(cor)
    if linha:
        f.line.color.rgb = rgb(linha)
        f.line.width = Pt(1)
    else:
        f.line.fill.background()
    f.shadow.inherit = False
    if nome:
        f.name = nome
    return f


def cartao(s, x, y, w, h, cor=FUNDO, linha=None):
    f = forma(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, cor, linha)
    f.adjustments[0] = min(0.12, 0.16 / min(w, h))
    return f


def ponto(s, x, y, d, cor, rotulo=None, tam=14, cor_texto=BRANCO):
    f = forma(s, MSO_SHAPE.OVAL, x, y, d, d, cor)
    if rotulo:
        tf = f.text_frame
        for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, m, 0)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = rotulo
        r.font.name, r.font.size, r.font.bold = FONTE, Pt(tam), True
        r.font.color.rgb = rgb(cor_texto)
    return f


def titulo(s, t, sub=None, cor=TINTA):
    texto(s, 0.6, 0.42, 12.1, 0.75, t, tam=30, negrito=True, cor=cor, ancora=MSO_ANCHOR.MIDDLE, nome="Título")
    if sub:
        texto(s, 0.6, 1.2, 12.1, 0.45, sub, tam=15, cor=TINTA2 if cor == TINTA else VERDE_CLARO)


def rodape(s, t, n):
    texto(s, 0.6, 6.98, 11.2, 0.3, t, tam=10, cor=TINTA2)
    texto(s, 12.1, 6.98, 0.65, 0.3, str(n), tam=10, cor=TINTA2, alinh=PP_ALIGN.RIGHT)


def marca(s, x, y, escala=1.0):
    """Motivo visual do projeto: pontos do mapa de risco (baixo, atenção, alto)."""
    for dx, dy, d, cor in [(0, 0.34, 0.2, CINZA_PONTO), (0.3, 0.14, 0.3, AMBAR), (0.72, 0, 0.44, VERMELHO)]:
        forma(s, MSO_SHAPE.OVAL, x + dx * escala, y + dy * escala, d * escala, d * escala, cor)


def seta(s, x1, y1, x2, y2, cor=TINTA2):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(cor)
    c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd",
                             {"type": "triangle", "w": "med", "len": "med"}))
    return c


def estilo_grafico(ch, legenda=False):
    ch.font.name, ch.font.size = FONTE, Pt(12)
    ch.font.color.rgb = rgb(TINTA2)
    ch.has_legend = legenda
    ch.has_title = False
    if legenda:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb("DDE3DF")
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(12)
    ch.category_axis.format.line.color.rgb = rgb("B9C2BC")
    ch.category_axis.has_major_gridlines = False
    ch.category_axis.tick_labels.font.size = Pt(12)


# --------------------------------------------------------------------- dados
pam = pd.read_csv(RAIZ / "data" / "producao_pam.csv").sort_values(["cod_mun", "cultura", "ano"])
ref = pam.groupby(["cod_mun", "cultura"])["rendimento_kg_ha"].transform(
    lambda v: v.shift(1).rolling(5, min_periods=3).mean())
base = pam[ref > 0].assign(quebra=(pam["rendimento_kg_ha"] < 0.5 * ref)[ref > 0])
quebra_ano = (base.groupby("ano")["quebra"].mean() * 100).round(0)
anual = pam.groupby("ano")[["area_plantada_ha", "area_colhida_ha"]].sum()
nao_colhido_2012 = (anual.loc[2012, "area_plantada_ha"] - anual.loc[2012, "area_colhida_ha"]) / 1e6
area_media = anual.loc[2020:2025, "area_plantada_ha"].mean() / 1e6
prev = pd.read_csv(RAIZ / "notebook" / "previsoes_teste.csv")
mun_com_quebra = prev.groupby("cod_mun")["quebra_real"].max().mean()
n_mun = pam["cod_mun"].nunique()
br = lambda v, casas=1: f"{v:.{casas}f}".replace(".", ",")
milhar = lambda v: f"{int(v):,}".replace(",", ".")
# safra atual (previsão ainda sem resultado oficial) e chuva recente
atual = pd.read_csv(RAIZ / "data" / "previsoes_safra_2026.csv")
ANO_ATUAL = int(atual["ano"].iloc[0])
pct_alto_atual = atual["alerta"].mean()
chuva_ate = json.loads((RAIZ / "app" / "data" / "chuva_diaria.json").read_text())["dados_ate"]
CHUVA_ATE = f"{chuva_ate[8:10]}/{chuva_ate[5:7]}/{chuva_ate[:4]}"
# o mesmo município que aparece na captura do aviso (prototipo/slides/s4_aviso.png)
EXEMPLO = next(d for d in dados_app.filtrar(ANO_ATUAL, "milho") if d["municipio"] == "Delmiro Gouveia")
SMS_EXEMPLO = montar_mensagens(EXEMPLO)["sms"]

# ===================================================================== 1 capa
s = novo(VERDE_ESC, "Abertura: apresentar o grupo e a ideia em uma frase — avisar o agricultor familiar "
                    "do Semiárido antes que a safra se perca.")
marca(s, 0.75, 0.8, 1.5)
texto(s, 0.75, 1.95, 8.5, 1.1, "Safra Sentinela", tam=60, negrito=True, cor=BRANCO, nome="Título")
texto(s, 0.75, 3.1, 7.6, 1.0, "Alerta de quebra de safra para a agricultura familiar do Semiárido",
      tam=22, cor=VERDE_CLARO)
texto(s, 0.75, 6.35, 7.6, 0.6, [[("Global Solution 2026/2 · CitizenTech", {"negrito": True, "cor": BRANCO})],
                               "Turma 2TSCOA · Grupo RHEAL (Grupo 42)"], tam=14, cor=VERDE_CLARO, espaco=2)
cartao(s, 8.75, 1.95, 3.95, 4.5, "1F3A2B")
texto(s, 9.05, 2.2, 3.4, 0.35, "EQUIPE", tam=12, negrito=True, cor=AMBAR)
y = 2.7
for nome, rm, resp in EQUIPE:
    texto(s, 9.05, y, 3.4, 0.62, [[(nome, {"negrito": True, "cor": BRANCO})],
                                   rm + (" · aluno responsável" if resp else "")],
          tam=13, cor=VERDE_CLARO, espaco=1)
    y += 0.72

# ================================================================ 2 problema
s = novo(notas="O problema: lavoura de sequeiro depende só da chuva. Mostrar o pico de 2012 no gráfico e "
               "dizer que o agricultor só descobre a perda quando já plantou tudo.")
titulo(s, "No Semiárido, uma estação de chuva ruim leva a safra da família",
       "Território: " + f"{n_mun:,}".replace(",", ".")
       + " municípios do Semiárido brasileiro, onde feijão e milho dependem só da chuva")
stats = [(f"{quebra_ano[2012]:.0f}%", "das lavouras municipais de feijão e milho tiveram quebra na seca de 2012", VERMELHO),
         (f"{br(nao_colhido_2012)} mi ha", "plantados em 2012 não chegaram a ser colhidos", AMBAR),
         (f"{mun_com_quebra * 100:.0f}%", "dos municípios tiveram ao menos uma quebra entre 2020 e 2025", VERDE)]
y = 1.95
for valor, legenda, cor in stats:
    cartao(s, 0.6, y, 4.3, 1.45)
    ponto(s, 0.85, y + 0.25, 0.26, cor)
    texto(s, 1.3, y + 0.12, 3.4, 0.65, valor, tam=34, negrito=True)
    texto(s, 1.3, y + 0.78, 3.4, 0.6, legenda, tam=13, cor=TINTA2)
    y += 1.62
texto(s, 5.35, 1.95, 7.3, 0.4, "Lavouras municipais com quebra de safra, por ano (%)", tam=15, negrito=True)
dados = CategoryChartData()
dados.categories = [str(a) for a in quebra_ano.index]
dados.add_series("% com quebra", [float(v) for v in quebra_ano.values])
g = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.25), Inches(2.35), Inches(7.5), Inches(4.35), dados).chart
estilo_grafico(g)
serie = g.plots[0].series[0]
g.plots[0].gap_width = 45
serie.format.fill.solid()
serie.format.fill.fore_color.rgb = rgb(VERDE)
for i, ano in enumerate(quebra_ano.index):
    if quebra_ano[ano] >= 30:
        pt = serie.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(VERMELHO)
        dl = pt.data_label
        dl.has_text_frame = True
        dl.text_frame.text = f"{quebra_ano[ano]:.0f}%"
        dl.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        dl.text_frame.paragraphs[0].runs[0].font.bold = True
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
rodape(s, "Fonte: IBGE, Produção Agrícola Municipal (2000–2025). Quebra = rendimento abaixo de 50% da média "
          "dos 5 anos anteriores do município. Em vermelho, anos com 30% ou mais.", 2)

# ================================================================= 3 persona
s = novo(notas="Persona ilustrativa. Reforçar: celular simples, sinal fraco, pouca leitura — a solução "
               "precisa chegar até ela, não o contrário.")
titulo(s, "Para quem: Dona Francisca, agricultora familiar no Cariri paraibano")
cartao(s, 0.6, 1.6, 4.1, 5.1, VERDE_ESC)
ponto(s, 1.95, 1.95, 1.4, AMBAR, "DF", tam=36, cor_texto=VERDE_ESC)
texto(s, 0.9, 3.55, 3.5, 0.5, "Dona Francisca, 52 anos", tam=20, negrito=True, cor=BRANCO, alinh=PP_ALIGN.CENTER)
texto(s, 0.9, 4.05, 3.5, 1.2, ["Monteiro (PB) · 4 hectares de milho e feijão", "Planta com a família, sem irrigação",
                                "Celular simples, sinal só na sede do sítio"],
      tam=14, cor=VERDE_CLARO, alinh=PP_ALIGN.CENTER, espaco=3)
texto(s, 0.9, 5.45, 3.5, 1.0, "“Eu só fico sabendo que a safra não vinga quando já plantei tudo.”",
      tam=15, italico=True, cor=BRANCO, alinh=PP_ALIGN.CENTER)
blocos = [("Do que ela precisa", VERDE, ["Saber cedo se o ano é de risco para a lavoura",
                                           "Orientação prática: o que fazer agora",
                                           "Acesso ao técnico e ao seguro a tempo"]),
          ("O que dificulta hoje", VERMELHO, ["Decide só pela experiência e pela conversa com vizinhos",
                                              "Previsões do tempo são genéricas e difíceis de entender",
                                              "Internet instável e pouca prática com aplicativos",
                                              "A ajuda oficial chega meses depois da perda"])]
x = 5.1
for cab, cor, itens in blocos:
    cartao(s, x, 1.6, 3.65, 5.1)
    ponto(s, x + 0.3, 1.9, 0.3, cor)
    texto(s, x + 0.75, 1.85, 2.7, 0.4, cab, tam=18, negrito=True)
    texto(s, x + 0.3, 2.65, 3.05, 3.9, itens, tam=17, espaco=18)
    x += 3.95
rodape(s, "Persona ilustrativa, construída a partir do perfil da agricultura familiar de sequeiro no Semiárido.", 3)

# ============================================================= 4 ecossistema
s = novo(notas="Quem ganha e quem faz funcionar. Destacar sindicatos e rádios: são a ponte de confiança "
               "com quem não tem celular.")
titulo(s, "Quem é beneficiado e quem faz a solução funcionar")
texto(s, 0.6, 1.5, 6, 0.35, "QUEM USA E É BENEFICIADO", tam=12, negrito=True, cor=VERDE)
usam = [("Agricultores familiares", "Recebem o aviso de risco e orientações simples no celular ou pelo rádio."),
        ("Técnicos de extensão rural", "Veem o mapa e a lista de municípios para visitar primeiro."),
        ("Gestores públicos", "Antecipam sementes, assistência e o Garantia-Safra onde o risco é maior.")]
x = 0.6
for cab, desc in usam:
    cartao(s, x, 1.9, 3.9, 1.85, VERDE_ESC)
    texto(s, x + 0.3, 2.08, 3.3, 0.4, cab, tam=18, negrito=True, cor=BRANCO)
    texto(s, x + 0.3, 2.6, 3.3, 1.05, desc, tam=14, cor=VERDE_CLARO)
    x += 4.1
texto(s, 0.6, 4.1, 6, 0.35, "QUEM PARTICIPA DO ECOSSISTEMA", tam=12, negrito=True, cor=VERDE)
participam = [("IBGE e NASA", "Dados abertos de produção agrícola e de clima por satélite."),
              ("Sindicatos e cooperativas", "Cadastram os agricultores e dão credibilidade ao aviso."),
              ("Rádios comunitárias", "Levam o alerta a quem não tem celular ou sinal."),
              ("Operadoras e WhatsApp", "Canal de entrega das mensagens de texto e áudio.")]
x = 0.6
for cab, desc in participam:
    cartao(s, x, 4.5, 2.875, 2.1)
    texto(s, x + 0.25, 4.68, 2.4, 0.7, cab, tam=16, negrito=True)
    texto(s, x + 0.25, 5.4, 2.4, 1.1, desc, tam=14, cor=TINTA2)
    x += 3.075
rodape(s, "", 4)

# ================================================================= 5 solução
s = novo(notas="Explicar os três passos: medir, prever, avisar. O mesmo cálculo serve a dois públicos: "
               "mensagem simples para o agricultor e mapa para o técnico.")
titulo(s, "A solução: do satélite ao celular do agricultor em três passos")
passos = [("1", "Medir", "Chuva, temperatura e umidade do solo medidas por satélite, mais o histórico de "
                         "safras de cada município.", VERDE),
          ("2", "Prever", "Um modelo de Machine Learning estima a chance de quebra de safra por município e "
                          "por cultura.", AMBAR),
          ("3", "Avisar", "O agricultor recebe um aviso simples; o técnico recebe o mapa de prioridades.", VERMELHO)]
x = 0.6
for n, cab, desc, cor in passos:
    cartao(s, x, 1.6, 3.75, 2.55)
    ponto(s, x + 0.3, 1.85, 0.62, cor, n, tam=22, cor_texto=VERDE_ESC if cor == AMBAR else BRANCO)
    texto(s, x + 1.1, 1.92, 2.4, 0.5, cab, tam=22, negrito=True)
    texto(s, x + 0.3, 2.7, 3.2, 1.35, desc, tam=14, cor=TINTA2)
    if n != "3":
        seta(s, x + 3.82, 2.87, x + 4.13, 2.87)
    x += 4.2
texto(s, 0.6, 4.5, 6, 0.35, "PRINCIPAIS FUNCIONALIDADES", tam=12, negrito=True, cor=VERDE)
funcs = [("Alerta no celular", "WhatsApp, SMS e áudio, com três ações práticas."),
         ("Mapa de risco", "Três níveis por município e lista de prioridades de visita."),
         ("Chuva quase em tempo real", "Chuva de cada dia, com cerca de 3 dias de atraso."),
         ("Análises e assistente", "Conferência com o resultado real e perguntas em linguagem simples.")]
x = 0.6
for cab, desc in funcs:
    ponto(s, x, 5.02, 0.22, VERDE)
    texto(s, x + 0.35, 4.93, 2.6, 0.4, cab, tam=16, negrito=True)
    texto(s, x + 0.35, 5.38, 2.6, 1.2, desc, tam=14, cor=TINTA2)
    x += 3.1
rodape(s, "", 5)

# ===================================================== 6 dados/acessibilidade
s = novo(notas="Dados públicos e gratuitos. Acessibilidade: funciona por SMS sem internet, tem áudio para "
               "quem não lê e rádio para quem não tem celular.")
titulo(s, "Dados públicos entram, informação simples sai")
texto(s, 0.6, 1.5, 6, 0.35, "DADOS UTILIZADOS", tam=12, negrito=True, cor=VERDE)
fontes = [("IBGE — Produção Agrícola Municipal", "Área, produção e rendimento de feijão e milho, 2000–2025"),
          ("NASA POWER", "Clima mensal para o modelo e chuva diária para o acompanhamento"),
          ("IBGE — delimitação do Semiárido", "Lista oficial dos municípios atendidos")]
y = 1.9
for cab, desc in fontes:
    cartao(s, 0.6, y, 5.6, 0.95)
    texto(s, 0.85, y + 0.12, 5.1, 0.35, cab, tam=15, negrito=True)
    texto(s, 0.85, y + 0.5, 5.1, 0.35, desc, tam=13, cor=TINTA2)
    y += 1.08
texto(s, 0.6, 5.3, 6, 0.35, "INFORMAÇÃO ENTREGUE", tam=12, negrito=True, cor=VERDE)
texto(s, 0.6, 5.7, 5.6, 1.1, ["Nível de risco de quebra por município e cultura",
                               "O que fazer: guardar semente, procurar o técnico, conferir o seguro",
                               "Chuva recente: 30 e 90 dias, e dias seguidos sem chuva"], tam=14, espaco=5)
cartao(s, 6.65, 1.5, 6.1, 5.3, VERDE_ESC)
texto(s, 6.95, 1.72, 5.5, 0.8, "Feita para quem tem pouco sinal, pouca leitura ou alguma deficiência",
      tam=19, negrito=True, cor=BRANCO)
acess = [("Sem internet", "versão SMS de até 160 caracteres"),
         ("Sem leitura", "o mesmo aviso em áudio"),
         ("Sem celular", "rádio comunitária e sindicato repassam o alerta"),
         ("Sem aplicativo", "nada para instalar ou atualizar"),
         ("Linguagem simples", "três ações numeradas, sem termos técnicos"),
         ("Baixa visão e daltonismo", "ícone e texto junto da cor, alto contraste")]
y = 2.75
for cab, desc in acess:
    ponto(s, 6.95, y + 0.07, 0.2, AMBAR)
    texto(s, 7.3, y, 5.2, 0.55, [[(cab + ": ", {"negrito": True, "cor": BRANCO}), (desc, {})]], tam=15, cor=VERDE_CLARO)
    y += 0.66
rodape(s, "", 6)

# ====================================================== 7 benefícios e medida
s = novo(notas="Benefícios para a família, para o técnico e para o território. Os indicadores já têm linha "
               "de base medida no teste do modelo; os de alcance serão medidos no piloto.")
titulo(s, "Benefícios para as pessoas e como vamos medir o impacto")
benef = [("Para a família", "Tempo para guardar semente e alimento, replantar ou acionar o seguro antes da perda."),
         ("Para técnicos e gestores", "Visitas e recursos direcionados aos municípios de maior risco."),
         ("Para o território", "Menos perdas, resposta mais rápida à seca e mais confiança na informação pública.")]
y = 1.6
for cab, desc in benef:
    cartao(s, 0.6, y, 4.6, 1.6)
    texto(s, 0.9, y + 0.15, 4.0, 0.4, cab, tam=17, negrito=True)
    texto(s, 0.9, y + 0.6, 4.0, 0.95, desc, tam=14, cor=TINTA2)
    y += 1.75
texto(s, 5.6, 1.6, 6, 0.35, "INDICADORES DE IMPACTO", tam=12, negrito=True, cor=VERDE)
indic = [("Quebras avisadas a tempo", "60% no teste (2020–2025)"),
         ("Alertas que se confirmam", "31% no teste"),
         ("Antecedência do aviso", "fim da estação chuvosa, antes da colheita"),
         ("Municípios cobertos", f"{n_mun:,}".replace(",", ".") + " do Semiárido"),
         (f"Safra {ANO_ATUAL} (previsão atual)", f"{pct_alto_atual:.0%} das {milhar(len(atual))} lavouras em risco alto"),
         ("Famílias cadastradas e alcançadas", "a medir no piloto"),
         ("Mensagens lidas ou ouvidas", "a medir no piloto")]
tab = s.shapes.add_table(len(indic) + 1, 2, Inches(5.6), Inches(2.0), Inches(7.15), Inches(4.6)).table
tab.columns[0].width, tab.columns[1].width = Inches(3.55), Inches(3.6)
for j, cab in enumerate(["Indicador", "Situação atual"]):
    c = tab.cell(0, j)
    c.text = cab
    c.fill.solid()
    c.fill.fore_color.rgb = rgb(VERDE_ESC)
    r = c.text_frame.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.bold = FONTE, Pt(14), True
    r.font.color.rgb = rgb(BRANCO)
for i, linha in enumerate(indic, start=1):
    for j, val in enumerate(linha):
        c = tab.cell(i, j)
        c.text = val
        c.fill.solid()
        c.fill.fore_color.rgb = rgb(FUNDO if i % 2 else BRANCO)
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = c.text_frame.paragraphs[0].runs[0]
        r.font.name, r.font.size, r.font.bold = FONTE, Pt(14), j == 0
        r.font.color.rgb = rgb(TINTA if j == 0 else TINTA2)
rodape(s, f"Quebras avisadas e alertas confirmados: teste do modelo (2020–2025). A safra de {ANO_ATUAL} ainda "
          "não tem resultado oficial.", 7)

# ===================================================================== 8 ODS
s = novo(notas="Três ODS com relação direta: fome zero, ação climática e redução das desigualdades.")
titulo(s, "Contribuição para os Objetivos de Desenvolvimento Sustentável")
ods = [("2", "DDA63A", "Fome zero e agricultura sustentável",
        "Protege a produção de alimentos e a renda de pequenos produtores (metas 2.3 e 2.4): o aviso permite "
        "reagir antes de a safra se perder."),
       ("13", "3F7E44", "Ação contra a mudança global do clima",
        "Aumenta a capacidade de adaptação a secas (meta 13.1) e leva alerta precoce a quem está mais exposto "
        "(meta 13.3)."),
       ("10", "DD1367", "Redução das desigualdades",
        "Leva ao agricultor familiar uma informação antes restrita à agricultura de grande escala, por canais "
        "que funcionam sem internet (meta 10.2).")]
x = 0.6
for num, cor, cab, desc in ods:
    cartao(s, x, 1.7, 3.9, 4.55)
    f = forma(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.35, 2.0, 1.25, 1.25, cor)
    f.adjustments[0] = 0.1
    texto(s, x + 0.35, 2.0, 1.25, 1.25, num, tam=40, negrito=True, cor=BRANCO, alinh=PP_ALIGN.CENTER, ancora=MSO_ANCHOR.MIDDLE)
    texto(s, x + 0.35, 3.5, 3.25, 0.85, f"ODS {num} — {cab}", tam=18, negrito=True)
    texto(s, x + 0.35, 4.4, 3.25, 1.8, desc, tam=15, cor=TINTA2)
    x += 4.1
rodape(s, "Metas citadas conforme a Agenda 2030 da ONU.", 8)

# ============================================================= 9 arquitetura
s = novo(notas="Seguir o fluxo da esquerda para a direita: fontes, coleta, armazenamento, modelo, API e os "
               "dois canais de saída. O que já existe no protótipo: coleta, modelo, API e painel.")
titulo(s, "Arquitetura: o caminho do dado, da origem até o usuário")
colunas = [("Fontes de dados", ["IBGE PAM\nprodução agrícola", "NASA POWER\nclima mensal e chuva diária", "IBGE\nmunicípios do Semiárido"], VERDE_CLARO, TINTA),
           ("Coleta e armazenamento", ["Python + Requests\nbaixa e padroniza os dados", "Arquivos CSV / SQLite\nguarda o histórico"], FUNDO, TINTA),
           ("Processamento e modelo", ["Pandas\ncria as variáveis de clima e histórico", "scikit-learn\nGradient Boosting estima o risco"], FUNDO, TINTA),
           ("Entrega", ["FastAPI\nserve risco e chuva recente", "Plataforma web\nmapa, análises e assistente", "Mensageria\nWhatsApp, SMS, áudio"], FUNDO, TINTA),
           ("Usuários", ["Técnicos e gestores", "Agricultores familiares", "Rádios e sindicatos"], VERDE_ESC, BRANCO)]
larg, x0, topo, alt_total = 2.2, 0.6, 2.05, 4.55
for i, (cab, caixas, cor, cor_t) in enumerate(colunas):
    x = x0 + i * (larg + 0.275)
    texto(s, x, 1.5, larg, 0.45, cab.upper(), tam=12, negrito=True, cor=VERDE, ancora=MSO_ANCHOR.BOTTOM)
    h = (alt_total - 0.2 * (len(caixas) - 1)) / len(caixas)
    for k, cx in enumerate(caixas):
        y = topo + k * (h + 0.2)
        cartao(s, x, y, larg, h, cor)
        partes = cx.split("\n")
        pars = [[(partes[0], {"negrito": True, "cor": cor_t, "tam": 15})]]
        if len(partes) > 1:
            pars.append([(partes[1], {"cor": VERDE_CLARO if cor == VERDE_ESC else TINTA2, "tam": 13})])
        texto(s, x + 0.15, y, larg - 0.3, h, pars, alinh=PP_ALIGN.CENTER, ancora=MSO_ANCHOR.MIDDLE, espaco=2)
    if i < len(colunas) - 1:
        seta(s, x + larg + 0.03, topo + alt_total / 2, x + larg + 0.25, topo + alt_total / 2)
rodape(s, "Proposta conceitual. Já implementados no protótipo: coleta, variáveis, modelo, API e plataforma web, "
          "com a chuva atualizada automaticamente. A mensageria está simulada.", 9)

# ====================================================== 10 protótipo: painel
s = novo(notas="Demonstração do painel: filtros, mapa de risco, lista de prioridades e detalhe do município. "
               "Dizer que é uma simulação com safras passadas, conferida com o resultado real.")
titulo(s, "Protótipo: o painel do técnico e do gestor")
s.shapes.add_picture(str(PROT / "s2_painel.png"), Inches(0.6), Inches(1.5), width=Inches(8.3))
notas_tela = [(f"Safra {ANO_ATUAL}, previsão atual", "Resumo da safra; o resultado oficial só sai no ano seguinte."),
              ("Mapa de risco", "Cada ponto é um município, em três níveis de risco."),
              ("Detalhe do município", "Chance de quebra, histórico das safras e a chuva de agora."),
              ("Filtros e busca", "Safra, cultura, estado e nome do município.")]
y = 1.5
for i, (cab, desc) in enumerate(notas_tela, start=1):
    ponto(s, 9.3, y + 0.03, 0.42, VERDE, str(i), tam=15)
    texto(s, 9.9, y, 2.85, 0.4, cab, tam=16, negrito=True)
    texto(s, 9.9, y + 0.42, 2.85, 0.8, desc, tam=14, cor=TINTA2)
    y += 1.3
rodape(s, f"Plataforma própria do Safra Sentinela, funcionando com dados reais. Na tela: Paraíba, milho, safra {ANO_ATUAL}.", 10)

# ==================================================== 11 protótipo: mensagem
s = novo(notas="A mensagem que chega ao agricultor: curta, com três ações, e deixando claro que é risco, "
               "não certeza. Mostrar a versão SMS.")
titulo(s, "Protótipo: o que chega ao celular do agricultor")
s.shapes.add_picture(str(PROT / "s4_aviso.png"), Inches(1.3), Inches(1.5), height=Inches(5.2))
x_txt = 6.9
texto(s, x_txt, 1.5, 5.8, 0.35, "COMO A MENSAGEM FOI PENSADA", tam=12, negrito=True, cor=VERDE)
texto(s, x_txt, 1.95, 5.8, 2.6, [[("Uma frase com o nível de risco", {"negrito": True}), (" e a cultura afetada.", {})],
                                  [("Três ações práticas", {"negrito": True}), (": guardar semente e alimento, procurar o técnico, conferir o Garantia-Safra.", {})],
                                  [("Honesta sobre a incerteza", {"negrito": True}), (": “é um aviso de risco, não uma certeza”.", {})],
                                  [("Áudio a um toque", {"negrito": True}), (" para quem não lê.", {})]], tam=15, espaco=10)
cartao(s, x_txt, 4.75, 5.85, 1.95, VERDE_ESC)
texto(s, x_txt + 0.3, 4.92, 5.3, 0.35, "VERSÃO SMS (celular simples, sem internet)", tam=12, negrito=True, cor=AMBAR)
texto(s, x_txt + 0.3, 5.35, 5.3, 1.25, SMS_EXEMPLO, tam=15, cor=BRANCO)
rodape(s, f"Aviso gerado pela plataforma para {EXEMPLO['municipio']} ({EXEMPLO['uf']}), milho, safra {ANO_ATUAL}. "
          "O áudio é ilustrativo.", 11)

# ============================ 12 protótipo: chuva recente e assistente
s = novo(notas="Dois recursos que aproximam a plataforma do dia a dia: a chuva medida por satélite, atualizada "
               "sozinha com cerca de três dias de atraso, e o assistente, que responde com os números do painel.")
titulo(s, "Protótipo: chuva quase em tempo real e assistente")
s.shapes.add_picture(str(PROT / "s3_chuva.png"), Inches(0.6), Inches(1.5), width=Inches(5.95))
s.shapes.add_picture(str(PROT / "s6_assistente.png"), Inches(6.8), Inches(1.5), width=Inches(5.95))
legendas = [(0.6, "Chuva dos últimos 90 dias", f"Cada município comparado com o normal do período, com dados até {CHUVA_ATE}. "
                                                "No detalhe, a chuva de cada dia e os dias seguidos sem chuva."),
            (6.8, "Assistente", "Responde sobre risco, chuva, histórico e o modelo, e lembra do contexto da conversa. "
                                "Não usa IA generativa: calcula a resposta sobre a mesma base do painel.")]
for x, cab, desc in legendas:
    texto(s, x, 5.45, 5.95, 0.4, cab, tam=17, negrito=True)
    texto(s, x, 5.9, 5.95, 1.0, desc, tam=14, cor=TINTA2)
rodape(s, "Chuva: NASA POWER, dados diários preliminares. Ela serve para acompanhamento e não entra no cálculo do risco.", 12)

# ================================================================= 12 modelo
s = novo(notas="Resultados do modelo no teste. Ser direto: avisa 6 em cada 10 quebras e supera a regra simples "
               "da chuva, mas 7 em cada 10 alertas não se confirmam. Por isso a mensagem fala em risco.")
titulo(s, "O que o modelo consegue hoje: avisa 6 em cada 10 quebras")
texto(s, 0.6, 1.5, 7.2, 0.4, "Desempenho no teste, safras de 2020 a 2025 (%)", tam=15, negrito=True)
dados = CategoryChartData()
dados.categories = list(MODELOS)
dados.add_series("Quebras avisadas (recall)", [v[0] * 100 for v in MODELOS.values()])
dados.add_series("Alertas confirmados (precisão)", [v[1] * 100 for v in MODELOS.values()])
g = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.9), Inches(7.4), Inches(4.85), dados).chart
estilo_grafico(g, legenda=True)
g.legend.font.size = Pt(12)
g.value_axis.maximum_scale = 80
g.plots[0].gap_width, g.plots[0].overlap = 70, -8
for serie, cor in zip(g.plots[0].series, (VERDE, AMBAR)):
    serie.format.fill.solid()
    serie.format.fill.fore_color.rgb = rgb(cor)
g.plots[0].has_data_labels = True
dl = g.plots[0].data_labels
dl.number_format, dl.number_format_is_linked = '0', False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size, dl.font.color.rgb = Pt(12), rgb(TINTA)
destaques = [("60%", "das quebras reais foram avisadas pelo modelo escolhido (Gradient Boosting)", VERDE),
             ("1,8×", "melhor que a regra simples “choveu pouco” em separar quem quebra de quem não quebra (PR-AUC)", AMBAR),
             ("31%", "dos alertas se confirmam: por isso o aviso fala em risco, não em certeza", VERMELHO)]
y = 1.5
for valor, legenda, cor in destaques:
    cartao(s, 8.3, y, 4.45, 1.62)
    ponto(s, 8.55, y + 0.28, 0.26, cor)
    texto(s, 9.0, y + 0.12, 3.6, 0.6, valor, tam=32, negrito=True)
    texto(s, 9.0, y + 0.78, 3.6, 0.8, legenda, tam=13, cor=TINTA2)
    y += 1.75
rodape(s, f"Treino: 2003–2019. Teste: 2020–2025, nunca visto pelo modelo. Para a safra de {ANO_ATUAL}, o mesmo "
          "modelo é reajustado com 2003–2025.", 13)

# ====================================================== 13 uso responsável
s = novo(notas="LGPD: coletamos o mínimo. Vieses: mostramos os que encontramos — Ceará, lavouras pequenas e "
               "feijão — e o que faremos antes de operar.")
titulo(s, "Uso responsável dos dados: privacidade, segurança e vieses")
cols = [("Privacidade (LGPD)", VERDE, ["Só três dados pessoais: telefone, município e cultura",
                                        "Cadastro com consentimento; sair a qualquer momento respondendo SAIR",
                                        "Sem CPF, renda ou localização exata",
                                        "O risco é calculado por município, com dados públicos"]),
        ("Segurança", AMBAR, ["Telefones guardados com criptografia",
                              "Acesso ao painel por perfil (técnico, gestor)",
                              "Dados apagados quando o agricultor sai do serviço",
                              "Registro de quem consultou o quê"]),
        ("Vieses encontrados", VERMELHO, ["Ceará: 30% das quebras avisadas; Bahia: 77%",
                                          "Lavouras menores: 49% das quebras avisadas",
                                          "Feijão: 51%; milho: 68%",
                                          "Antes de operar: ajustar o limiar por região e acompanhar cada grupo"])]
x = 0.6
for cab, cor, itens in cols:
    cartao(s, x, 1.6, 3.9, 3.95)
    ponto(s, x + 0.3, 1.9, 0.3, cor)
    texto(s, x + 0.75, 1.85, 3.0, 0.4, cab, tam=18, negrito=True)
    texto(s, x + 0.3, 2.55, 3.3, 2.9, itens, tam=15, espaco=10)
    x += 4.1
cartao(s, 0.6, 5.75, 12.1, 0.95, VERDE_ESC)
texto(s, 0.9, 5.75, 11.5, 0.95, [[("Compromisso com o agricultor: ", {"negrito": True, "cor": BRANCO}),
                                   ("todo aviso diz que é um risco, não uma certeza, e quem não tem celular "
                                    "é alcançado pelo rádio e pelo sindicato.", {})]],
      tam=15, cor=VERDE_CLARO, ancora=MSO_ANCHOR.MIDDLE)
rodape(s, "Vieses medidos no conjunto de teste (2020–2025) do modelo escolhido. O modelo usa a média do município, "
          "não a situação de cada família.", 14)

# ============================================================================
# APÊNDICE TÉCNICO — para leitores de Ciência de Dados
# Os números de validação e de teste repetem as tabelas do notebook (seções 5, 6 e 7).
# ============================================================================
FONTE_FORMULA = "Cambria"
CV_PRAUC = {"Regressão Logística": 0.489, "Random Forest": 0.471, "Gradient Boosting": 0.497}
LIMIARES = {"Regressão Logística": 0.571, "Random Forest": 0.296, "Gradient Boosting": 0.509}
TESTE = {  # recall, precisão, F1, acurácia, PR-AUC, ROC-AUC, % alertadas
    "Regressão Logística": (0.551, 0.320, 0.405, 0.742, 0.337, 0.738, 0.274),
    "Random Forest": (0.650, 0.266, 0.377, 0.659, 0.329, 0.714, 0.389),
    "Gradient Boosting": (0.600, 0.306, 0.405, 0.720, 0.371, 0.742, 0.312),
    "Regra da chuva": (0.578, 0.199, 0.296, 0.564, 0.207, 0.601, 0.461),
}
IMPORTANCIA = [("latitude", 0.055), ("estado (uf)", 0.029), ("variabilidade do rendimento", 0.028),
               ("rendimento do ano anterior", 0.027), ("rendimento de referência", 0.016),
               ("desvio da temp. máxima, mês 3", 0.016), ("chuva dos meses 1 e 2", 0.014),
               ("chuva do mês 4", 0.012), ("umidade do ar, mês 3", 0.007), ("longitude", 0.006)]
CENARIOS_TEC = [("A, antes do plantio", "histórico + 3 meses antes das chuvas", 0.739, 0.197, 0.246),
                ("B, meio da estação", "A + 2 primeiros meses de chuva", 0.738, 0.239, 0.294),
                ("C, fim da estação", "B + 2 últimos meses de chuva", 0.600, 0.306, 0.371)]
EQUIDADE = [("Bahia", "3.376", "15%", "77%", "22%"), ("Paraíba", "2.376", "28%", "75%", "44%"),
            ("Piauí", "2.592", "19%", "65%", "32%"), ("Pernambuco", "1.490", "17%", "57%", "29%"),
            ("Rio Grande do Norte", "1.743", "21%", "46%", "41%"), ("Ceará", "2.100", "16%", "30%", "27%"),
            ("Menores áreas (1º quartil)", "4.328", "11%", "49%", "29%"),
            ("Maiores áreas (4º quartil)", "4.325", "18%", "58%", "30%"),
            ("Feijão", "8.684", "15%", "51%", "30%"), ("Milho", "8.626", "16%", "68%", "31%")]
BLOCOS_2026 = [("2012–2013", "87%", "64%"), ("2014–2015", "87%", "31%"), ("2016–2017", "76%", "40%"),
               ("2018–2019", "55%", "28%"), ("2020–2021", "70%", "18%"), ("2022–2023", "54%", "27%"),
               ("2024–2025", "65%", "44%")]
dec = lambda v, casas=2: f"{v:.{casas}f}".replace(".", ",")

# calibração: medida na tabela de previsões do teste (pontuação bruta × probabilidade calibrada)
teste_prev = pd.read_csv(RAIZ / "notebook" / "previsoes_teste.csv")
_y, _s, _p = teste_prev["quebra_real"].to_numpy(), teste_prev["pontuacao"].to_numpy(), teste_prev["prob_quebra"].to_numpy()
_lg = lambda v: np.log(np.clip(v, 1e-6, 1 - 1e-6) / (1 - np.clip(v, 1e-6, 1 - 1e-6)))
PLATT_A, PLATT_B = np.polyfit(_lg(_s), _lg(_p), 1)        # a calibração é linear no logit: recupera a e b


def _ece(y, p):
    t = (pd.DataFrame({"y": y, "p": p}).assign(f=lambda d: pd.qcut(d["p"], 10, duplicates="drop"))
         .groupby("f", observed=True).agg(y=("y", "mean"), p=("p", "mean"), n=("y", "size")))
    return float((t["n"] / t["n"].sum() * (t["y"] - t["p"]).abs()).sum())


BRIER = {"bruta": float(((_s - _y) ** 2).mean()), "cal": float(((_p - _y) ** 2).mean()),
         "ref": float(((0.21 - _y) ** 2).mean())}
ECE = {"bruta": _ece(_y, _s), "cal": _ece(_y, _p)}
MEDIA = {"bruta": float(_s.mean()), "cal": float(_p.mean()), "real": float(_y.mean())}
LIMIAR_PROB = float(teste_prev.loc[teste_prev["alerta"] == 1, "prob_quebra"].min())
_dec10 = (pd.DataFrame({"y": _y, "p": _p}).assign(f=lambda d: pd.qcut(d["p"], 10))
          .groupby("f", observed=True).agg(p=("p", "mean"), y=("y", "mean")))
TOPO_PREV, TOPO_REAL = float(_dec10["p"].iloc[-1]), float(_dec10["y"].iloc[-1])


def formula(s, x, y, w, h, linhas, tam=16, rotulo=None):
    """Caixa de fórmula: fundo claro e fonte serifada, para separar a matemática do texto."""
    cartao(s, x, y, w, h, FUNDO)
    topo = y + 0.12
    if rotulo:
        texto(s, x + 0.25, topo, w - 0.5, 0.3, rotulo, tam=11, negrito=True, cor=VERDE)
        topo += 0.34
    cx = texto(s, x + 0.25, topo, w - 0.5, h - (topo - y) - 0.1, linhas, tam=tam, espaco=5,
               ancora=MSO_ANCHOR.MIDDLE if not rotulo else MSO_ANCHOR.TOP)
    for par in cx.text_frame.paragraphs:
        for r in par.runs:
            r.font.name = FONTE_FORMULA
    return cx


def tabela(s, x, y, w, h, cabecalho, linhas, larguras=None, tam=12, destaque=None, primeira_negrito=True):
    t = s.shapes.add_table(len(linhas) + 1, len(cabecalho), Inches(x), Inches(y), Inches(w), Inches(h)).table
    if larguras:
        for j, lg in enumerate(larguras):
            t.columns[j].width = Inches(lg)
    for j, cab in enumerate(cabecalho):
        c = t.cell(0, j)
        c.text = cab or " "
        c.fill.solid(); c.fill.fore_color.rgb = rgb(VERDE_ESC)
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = c.text_frame.paragraphs[0].runs[0]
        r.font.name, r.font.size, r.font.bold = FONTE, Pt(tam), True
        r.font.color.rgb = rgb(BRANCO)
    for i, linha in enumerate(linhas, start=1):
        for j, val in enumerate(linha):
            c = t.cell(i, j)
            c.text = str(val)
            c.fill.solid()
            c.fill.fore_color.rgb = rgb(VERDE_CLARO if destaque == i - 1 else (FUNDO if i % 2 else BRANCO))
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.margin_top = c.margin_bottom = Inches(0.03)
            for par in c.text_frame.paragraphs:
                for r in par.runs:
                    r.font.name, r.font.size = FONTE, Pt(tam)
                    r.font.bold = (j == 0 and primeira_negrito) or destaque == i - 1
                    r.font.color.rgb = rgb(TINTA)
    return t


def topicos(s, x, y, w, itens, tam=14, espaco=9):
    """Lista de tópicos com rótulo em negrito: [(rótulo, texto), …]."""
    pars = [[(rot + (" " if txt else ""), {"negrito": True}), (txt, {"cor": TINTA2})] for rot, txt in itens]
    return texto(s, x, y, w, 5.0, pars, tam=tam, espaco=espaco)


n_pag = 14   # as páginas do apêndice continuam a numeração

# ---------------------------------------------------------------- divisória
s = novo(VERDE_ESC, "A partir daqui, o detalhamento técnico para quem quer conferir o método.")
marca(s, 0.75, 0.8, 1.5)
texto(s, 0.75, 2.3, 11.5, 1.0, "Apêndice técnico", tam=48, negrito=True, cor=BRANCO, nome="Título")
texto(s, 0.75, 3.45, 9.5, 1.6, "Formulação do problema, construção das variáveis, validação, modelos e "
                                "hiperparâmetros, calibração, resultados, equidade e arquitetura. "
                                "Cada escolha vem com a fórmula e com o motivo.", tam=20, cor=VERDE_CLARO)
texto(s, 0.75, 6.35, 11.5, 0.5, "O notebook e o README do projeto trazem o código e as mesmas contas, passo a passo.",
      tam=14, cor=VERDE_CLARO)
n_pag += 1

# ------------------------------------------------------------- A1 formulação
s = novo(notas="Formulação: classificação binária por lavoura municipal. O limite é relativo ao próprio "
               "histórico do município e usa só o passado.")
titulo(s, "Formulação: o que exatamente o modelo prevê")
formula(s, 0.6, 1.5, 6.3, 2.05, [
    "r_ref(m, c, t) = média{ r(m, c, t−1), …, r(m, c, t−5) }",
    "quebra(m, c, t) = 1   se   r(m, c, t) < 0,5 · r_ref(m, c, t)",
    [("r: rendimento em kg/ha  ·  m: município  ·  c: cultura  ·  t: ano  ·  mínimo de 3 anos em r_ref", {"tam": 12, "cor": TINTA2})],
], rotulo="VARIÁVEL-ALVO")
fatos = [("66.236", "observações (município, cultura, ano)"), ("2003–2025", "safras modeladas"),
         ("19,7%", "de quebras (feijão 17,3%; milho 22,0%)"), ("Binária", "classificação supervisionada")]
x = 0.6
for valor, legenda in fatos:
    cartao(s, x, 3.8, 1.5, 1.55)
    texto(s, x + 0.12, 3.92, 1.3, 0.45, valor, tam=18, negrito=True)
    texto(s, x + 0.12, 4.42, 1.3, 0.9, legenda, tam=11, cor=TINTA2)
    x += 1.6
texto(s, 0.6, 5.6, 6.3, 1.2, "Lavouras com plantio e colheita zero entram com r = 0, portanto como quebra: são as "
                             "perdas totais, o caso mais grave. Os anos de 2000 a 2002 servem só para formar a referência.",
      tam=13, cor=TINTA2)
texto(s, 7.3, 1.5, 5.4, 0.35, "POR QUE ESTA DEFINIÇÃO", tam=12, negrito=True, cor=VERDE)
topicos(s, 7.3, 1.95, 5.4, [
    ("Limite relativo.", "O rendimento médio varia cerca de oito vezes entre municípios. Um corte em kg/ha "
                         "marcaria como quebra permanente quem produz pouco."),
    ("50%.", "É o gatilho de perda do Garantia-Safra: o alvo tem significado prático."),
    ("Só o passado.", "A referência usa anos anteriores a t. Pode ser calculada antes da safra e não vaza o alvo."),
    ("Classificação, não regressão.", "A decisão apoiada é binária (avisar ou não), e numa regressão o erro seria "
                                      "dominado pelo nível de produtividade, que é estável."),
])
n_pag += 1; rodape(s, "Fonte do rendimento: IBGE, Produção Agrícola Municipal, tabela SIDRA 5457.", n_pag)

# -------------------------------------------------------------- A2 variáveis
s = novo(notas="As 58 variáveis. O ponto central é alinhar o clima pela estação chuvosa de cada lugar e "
               "calcular o normal só com anos anteriores.")
titulo(s, "Variáveis: 58 preditoras, alinhadas à estação chuvosa local")
formula(s, 0.6, 1.5, 6.0, 1.55, [
    "s* = argmax ₛ  Σ ₖ₌₀…₃  P̄[(s + k) mod 12]",
    [("P̄: chuva média de cada mês, calculada só com os anos até 2019 (treino)", {"tam": 12, "cor": TINTA2})],
], rotulo="INÍCIO DA ESTAÇÃO CHUVOSA (janela de 4 meses mais chuvosa)")
formula(s, 0.6, 3.2, 6.0, 2.0, [
    "N(t) = média{ x(τ) : τ < t }",
    "desvio(t) = x(t) − N(t)",
    "% do normal(t) = 100 · x(t) / N(t)",
], rotulo="“NORMAL” SEM VAZAMENTO (média expansiva dos anos anteriores)")
texto(s, 0.6, 5.4, 6.0, 1.4, [
    [("Por que alinhar pela estação: ", {"negrito": True}),
     ("“chuva de março” significa coisas diferentes no Ceará e em Minas. “Segundo mês de chuva” é a mesma fase "
      "da lavoura em todo o território, e um único modelo serve aos 11 estados.", {"cor": TINTA2})],
    [("Por que o normal expansivo: ", {"negrito": True}),
     ("a média de todo o período levaria informação de anos futuros para dentro do treino.", {"cor": TINTA2})],
], tam=13, espaco=6)
tabela(s, 7.0, 1.5, 5.75, 3.55, ["Grupo", "Conteúdo", "Nº"], [
    ("Clima por mês", "7 meses (3 antes + 4 da estação) × 6 medidas: chuva, desvio da chuva, umidade do solo e seu "
                      "desvio, desvio da temperatura máxima, umidade do ar", "42"),
    ("Agregados de chuva", "antes da estação, meses 1–2 e estação inteira, em mm e em % do normal", "6"),
    ("Histórico", "rendimento de referência, do ano anterior, coeficiente de variação, quebras em 5 anos, "
                  "log(1 + área plantada anterior)", "5"),
    ("Localização", "latitude, longitude, mês de início das chuvas", "3"),
    ("Categóricas", "cultura e estado (one-hot: 69 colunas no total)", "2"),
], larguras=[1.55, 3.6, 0.6], tam=12)
texto(s, 7.0, 5.65, 5.75, 1.2, [
    [("Fonte do clima: ", {"negrito": True}),
     ("NASA POWER (reanálise MERRA-2), grade de 0,5° × 0,625°. Os 1.477 municípios caem em 331 células.", {"cor": TINTA2})],
    [("Nada do ano previsto além do clima: ", {"negrito": True}),
     ("área colhida, produção e rendimento do próprio ano não entram.", {"cor": TINTA2})],
], tam=13, espaco=6)
n_pag += 1; rodape(s, "Em cada célula, os meses pre3, pre2 e pre1 antecedem o início das chuvas; m1 a m4 são a estação.", n_pag)

# --------------------------------------------------------------- A3 validação
s = novo(notas="Validação: tudo respeita a ordem do tempo. O teste só é usado uma vez.")
titulo(s, "Validação: divisão cronológica e blocos de anos")
ANOS = list(range(2003, 2026))
x0, larg = 2.35, 0.292
linhas_val = [("Dobra 1", 2009, (2010, 2011)), ("Dobra 2", 2011, (2012, 2013)), ("Dobra 3", 2013, (2014, 2015)),
              ("Dobra 4", 2015, (2016, 2017)), ("Dobra 5", 2017, (2018, 2019)), ("Avaliação final", 2019, (2020, 2025))]
y = 1.65
for i, (rot, fim_treino, (v0, v1)) in enumerate(linhas_val):
    final = rot == "Avaliação final"
    if final:
        y += 0.18
    texto(s, 0.6, y, 1.7, 0.36, rot, tam=13, negrito=True, ancora=MSO_ANCHOR.MIDDLE)
    for k, ano in enumerate(ANOS):
        if ano <= fim_treino:
            cor_c = VERDE if final else "8FB9A3"
        elif v0 <= ano <= v1:
            cor_c = VERMELHO if final else AMBAR
        else:
            cor_c = "E4E9E5"
        forma(s, MSO_SHAPE.RECTANGLE, x0 + k * larg, y, larg - 0.03, 0.36, cor_c)
    y += 0.46
for k, ano in enumerate(ANOS):
    if ano % 2 == 1:
        texto(s, x0 + k * larg - 0.1, y + 0.02, larg + 0.2, 0.25, str(ano)[2:], tam=10, cor=TINTA2, alinh=PP_ALIGN.CENTER)
leg_x = 0.6
for cor_c, rot in [("8FB9A3", "treino da dobra"), (AMBAR, "validação da dobra"), (VERDE, "treino final (48.926 linhas)"),
                   (VERMELHO, "teste (17.310 linhas)")]:
    forma(s, MSO_SHAPE.RECTANGLE, leg_x, y + 0.5, 0.22, 0.22, cor_c)
    texto(s, leg_x + 0.3, y + 0.47, 2.2, 0.3, rot, tam=12, cor=TINTA2)
    leg_x += 2.15 if "final" not in rot else 2.75
topicos(s, 9.45, 1.6, 3.3, [
    ("Por que cronológica:", "a taxa de quebra vai de 5% a 60% conforme o ano. Numa divisão aleatória, o modelo "
                             "aprenderia “2012 foi seco” em vez da relação entre clima e perda."),
    ("Blocos de anos inteiros:", "nunca se treina e valida com lavouras da mesma safra."),
    ("Pré-processamento no pipeline:", "imputação, padronização e codificação são ajustadas só com o treino de cada dobra."),
], tam=13, espaco=10)
formula(s, 0.6, 5.55, 8.55, 1.25, [
    "wₖ = n / (2 · nₖ)      AP = Σₙ (Rₙ − Rₙ₋₁) · Pₙ      τ = max{ τ : recall(τ) ≥ 0,75 }",
    [("pesos de classe (1 quebra para 4 normais)  ·  PR-AUC, a métrica de seleção  ·  limiar, com o recall medido fora da amostra",
      {"tam": 12, "cor": TINTA2})],
], tam=15)
n_pag += 1; rodape(s, "PR-AUC em vez de acurácia: prever “nunca quebra” acerta 84% do teste sem avisar ninguém.", n_pag)

# ----------------------------------------------------------------- A4 modelos
s = novo(notas="Três modelos em escada de flexibilidade. Hiperparâmetros por busca em grade com as dobras temporais.")
titulo(s, "Modelos e hiperparâmetros")
tabela(s, 0.6, 1.5, 12.15, 4.45, ["", "Regressão Logística", "Random Forest", "Gradient Boosting (escolhido)"], [
    ("Classe (scikit-learn 1.9)", "LogisticRegression", "RandomForestClassifier", "HistGradientBoostingClassifier"),
    ("Parâmetros fixos", "penalidade L2, L-BFGS, max_iter = 2000, class_weight = balanced; variáveis padronizadas",
     "300 árvores, Gini, bootstrap, sem limite de profundidade, class_weight = balanced_subsample",
     "perda logarítmica, até 300 árvores, min_samples_leaf = 20, 255 faixas por variável, class_weight = balanced"),
    ("Grade testada", "C ∈ {0,01; 0,1; 1}", "min_samples_leaf ∈ {5; 20}  ×  max_features ∈ {√p; 0,3}",
     "learning_rate ∈ {0,03; 0,1}  ×  max_leaf_nodes ∈ {8; 31}"),
    ("Escolhido", "C = 0,01", "min_samples_leaf = 5, max_features = √p (8 de 69 colunas)",
     "learning_rate = 0,03, max_leaf_nodes = 8"),
    ("PR-AUC média nas 5 dobras", dec(CV_PRAUC["Regressão Logística"], 3), dec(CV_PRAUC["Random Forest"], 3),
     dec(CV_PRAUC["Gradient Boosting"], 3)),
    ("Limiar (recall de 75%)", dec(LIMIARES["Regressão Logística"], 3), dec(LIMIARES["Random Forest"], 3),
     dec(LIMIARES["Gradient Boosting"], 3)),
], larguras=[2.15, 3.2, 3.3, 3.5], tam=12)
texto(s, 0.6, 6.1, 12.15, 0.8, [
    [("Leitura: ", {"negrito": True}),
     ("a regressão escolheu a regularização mais forte e o boosting, a configuração mais conservadora (taxa baixa, "
      "árvores pequenas). É o comportamento esperado num problema ruidoso. O critério de escolha, a PR-AUC média "
      "das dobras, foi fixado antes de olhar o teste.", {"cor": TINTA2})]], tam=13)
n_pag += 1; rodape(s, "Busca em grade (GridSearchCV) com as cinco dobras temporais. Semente aleatória 42 em todos os modelos.", n_pag)

# ------------------------------------------------------------ A5 boosting
s = novo(notas="Como o Gradient Boosting soma árvores pequenas e por que a configuração conservadora venceu.")
titulo(s, "Como o Gradient Boosting funciona neste problema")
formula(s, 0.6, 1.5, 6.2, 2.75, [
    "F₀(x) = log-chance inicial",
    "Fₖ(x) = Fₖ₋₁(x) + ν · hₖ(x)          ν = 0,03",
    "p(x) = 1 / (1 + e^(−F_K(x)))          K = 300",
    [("hₖ: árvore de até 8 folhas, ajustada ao gradiente da perda na rodada k", {"tam": 12, "cor": TINTA2})],
], rotulo="MODELO ADITIVO")
formula(s, 0.6, 4.45, 6.2, 1.55, [
    "L = − Σᵢ wᵢ · [ yᵢ ln pᵢ + (1 − yᵢ) ln(1 − pᵢ) ]",
    [("wᵢ: peso da classe da lavoura i. Quebras pesam cerca de 2,4 e safras normais, 0,63", {"tam": 12, "cor": TINTA2})],
], rotulo="PERDA LOGARÍTMICA PONDERADA")
texto(s, 0.6, 6.15, 6.2, 0.7, "As variáveis numéricas são discretizadas em até 255 faixas (histogramas): o treino fica "
                              "rápido e os valores ausentes são tratados de forma nativa.", tam=13, cor=TINTA2)
texto(s, 7.2, 1.5, 5.5, 0.35, "POR QUE ESTA CONFIGURAÇÃO", tam=12, negrito=True, cor=VERDE)
topicos(s, 7.2, 1.95, 5.5, [
    ("Árvores pequenas (8 folhas).", "Capturam interações simples, como pouca chuva com solo já seco, sem decorar "
                                     "os anos de treino."),
    ("Taxa de aprendizado baixa (0,03).", "Cada árvore corrige pouco; o conjunto generaliza melhor para anos novos."),
    ("Pesos de classe.", "Fazem o modelo dar a mesma atenção às quebras, que são 1 em cada 5. O efeito colateral é "
                         "inflar a pontuação, corrigido depois pela calibração."),
    ("Parada antecipada.", "Fica ativa por padrão (10% do treino separado, paciência de 10 rodadas). Aqui o modelo "
                           "usou as 300 árvores."),
    ("Por que não uma rede neural.", "Com 49 mil linhas tabulares e ruído alto, árvores costumam igualar ou superar "
                                     "redes, com muito menos ajuste."),
], tam=13, espaco=8)
n_pag += 1; rodape(s, "Regressão Logística: p = σ(w·x + b), com penalidade ‖w‖²/(2C). Random Forest: média de 300 árvores independentes.", n_pag)

# -------------------------------------------------------------- A6 resultados
s = novo(notas="Resultados completos no teste. Os três modelos quase empatam e todos superam a regra da chuva.")
titulo(s, "Resultados no teste (2020–2025)")
linhas_res = [(nome, *[dec(v, 2) for v in vals[:6]], f"{vals[6]:.0%}") for nome, vals in TESTE.items()]
tabela(s, 0.6, 1.5, 7.9, 2.6, ["Modelo", "Recall", "Precisão", "F1", "Acurácia", "PR-AUC", "ROC-AUC", "Alertadas"],
       linhas_res, larguras=[2.05, 0.75, 0.85, 0.65, 0.9, 0.8, 0.85, 1.05], tam=12, destaque=2)
texto(s, 0.6, 4.25, 7.9, 0.6, "Limiar fixado na validação. Taxa real de quebra no teste: 15,9%, que é a PR-AUC de um "
                              "modelo sem informação.", tam=12, cor=TINTA2)
texto(s, 8.9, 1.5, 3.85, 0.35, "MATRIZ DE CONFUSÃO, GRADIENT BOOSTING", tam=12, negrito=True, cor=VERDE)
celulas_mc = [(0, 0, "10.807", "normais, sem alerta", FUNDO, TINTA), (1, 0, "3.751", "alertas falsos", "FBE6E1", TINTA),
              (0, 1, "1.101", "quebras sem aviso", "FBE6E1", TINTA), (1, 1, "1.651", "quebras avisadas", VERDE_CLARO, TINTA)]
for cx_, cy_, valor, legenda, fundo_c, cor_t in celulas_mc:
    cartao(s, 8.9 + cx_ * 1.95, 1.95 + cy_ * 1.12, 1.85, 1.02, fundo_c)
    texto(s, 8.9 + cx_ * 1.95 + 0.15, 2.0 + cy_ * 1.12, 1.6, 0.5, valor, tam=20, negrito=True, cor=cor_t)
    texto(s, 8.9 + cx_ * 1.95 + 0.15, 2.5 + cy_ * 1.12, 1.6, 0.4, legenda, tam=11, cor=TINTA2)
topicos(s, 0.6, 4.95, 12.15, [
    ("O aprendizado de máquina acrescenta informação.", "PR-AUC de 0,37, contra 0,21 da regra “choveu pouco” e 0,16 do "
     "acaso. Alertando 31% das lavouras, o modelo alcança 60% das quebras; a regra precisa alertar 46% para alcançar 58%."),
    ("Os três modelos quase empatam.", "O limite está nos dados (clima mensal em grade de 50 km, produção em média "
     "municipal), não no algoritmo."),
    ("O recall caiu de 75% (validação) para 60%.", "O limiar foi calibrado em 2010–2019, com 28% de quebras, e aplicado a "
     "um período com 16%. Em operação, ele precisa ser recalculado a cada safra."),
], tam=13, espaco=6)
n_pag += 1; rodape(s, "Sem intervalos de confiança: lavouras do mesmo ano são correlacionadas, e diferenças pequenas entre modelos não são significativas.", n_pag)

# -------------------------------------------------------------- A7 calibração
s = novo(notas="Calibração: a pontuação vinha inflada pelos pesos de classe. A curva de Platt, ajustada fora da "
               "amostra, transforma a pontuação em probabilidade sem mudar a ordem.")
titulo(s, "Calibração: da pontuação à probabilidade")
formula(s, 0.6, 1.5, 6.0, 1.75, [
    f"p = σ( a · logit(s) + b )        a = {dec(PLATT_A, 3)}   b = {dec(PLATT_B, 3)}",
    [("s: pontuação do modelo  ·  logit(s) = ln(s / (1 − s))  ·  σ: função logística", {"tam": 12, "cor": TINTA2})],
], rotulo="CALIBRAÇÃO DE PLATT (2 parâmetros, ajustados fora da amostra)")
formula(s, 0.6, 3.4, 6.0, 1.65, [
    "Brier = (1/n) Σᵢ (pᵢ − yᵢ)²",
    "ECE = Σ_g (n_g / n) · | ȳ_g − p̄_g |",
    [("g: dez grupos de mesmo tamanho, ordenados pela probabilidade prevista", {"tam": 12, "cor": TINTA2})],
], rotulo="COMO SE MEDE", tam=15)
tabela(s, 0.6, 5.2, 6.0, 1.55, ["No teste", "Pontuação bruta", "Calibrada"], [
    ("Probabilidade média prevista (real: " + f"{MEDIA['real']:.0%})", f"{MEDIA['bruta']:.0%}", f"{MEDIA['cal']:.0%}"),
    ("Brier (referência: " + dec(BRIER["ref"], 3) + ")", dec(BRIER["bruta"], 3), dec(BRIER["cal"], 3)),
    ("Erro de calibração (ECE)", dec(ECE["bruta"], 3), dec(ECE["cal"], 3)),
], larguras=[3.3, 1.45, 1.25], tam=12)
s.shapes.add_picture(str(RAIZ / "notebook" / "figuras" / "11_calibracao.png"), Inches(6.95), Inches(1.45), height=Inches(3.55))
topicos(s, 11.0, 1.5, 1.8, [("Por que Platt:", "é crescente, então não muda a ordem das lavouras nem o alerta.")], tam=12)
topicos(s, 6.95, 5.15, 5.8, [
    ("Escolha do método.", "Platt e isotônica foram comparadas dentro do treino, calibrando nos blocos anteriores e "
                           "medindo o Brier no seguinte."),
    ("O que ainda sobra.", f"No décimo de maior risco, a previsão média é {TOPO_PREV:.0%} e {TOPO_REAL:.0%} quebraram: a "
                           "calibração foi aprendida num período com mais quebras."),
    ("Limiar em probabilidade.", f"O alerta sai a partir de {LIMIAR_PROB:.0%} de chance de quebra."),
], tam=12, espaco=5)
n_pag += 1; rodape(s, "Brier de referência: prever para todas as lavouras a taxa de quebra do treino (21%).", n_pag)

# ------------------------------------------------- A8 importância e antecedência
s = novo(notas="Em que o modelo se apoia e quanto custa avisar antes.")
titulo(s, "O que o modelo usa e com quanta antecedência avisa")
texto(s, 0.6, 1.5, 6.1, 0.4, "Importância por permutação: queda na PR-AUC do teste", tam=15, negrito=True)
dados_g = CategoryChartData()
dados_g.categories = [n for n, _ in reversed(IMPORTANCIA)]
dados_g.add_series("Queda na PR-AUC", [v for _, v in reversed(IMPORTANCIA)])
g = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.9), Inches(6.3), Inches(4.0), dados_g).chart
estilo_grafico(g)
g.plots[0].gap_width = 45
g.plots[0].series[0].format.fill.solid()
g.plots[0].series[0].format.fill.fore_color.rgb = rgb(VERDE)
g.plots[0].has_data_labels = True
g.plots[0].data_labels.number_format, g.plots[0].data_labels.number_format_is_linked = "0.000", False
g.plots[0].data_labels.font.size = Pt(11)
g.value_axis.visible = False
g.value_axis.has_major_gridlines = False
g.category_axis.tick_labels.font.size = Pt(11)
texto(s, 0.6, 6.0, 6.1, 0.85, "Cada variável é embaralhada 5 vezes no teste. Ao contrário da importância interna das "
                              "árvores, a permutação mede o efeito em dados novos e não favorece variáveis com muitos "
                              "valores distintos.", tam=12, cor=TINTA2)
texto(s, 7.2, 1.5, 5.55, 0.4, "Antecedência: o mesmo modelo com menos informação", tam=15, negrito=True)
tabela(s, 7.2, 1.95, 5.55, 1.85, ["Cenário", "Informação", "Recall", "Precisão", "PR-AUC"],
       [(a, b, dec(c), dec(d), dec(e)) for a, b, c, d, e in CENARIOS_TEC],
       larguras=[1.45, 1.9, 0.7, 0.8, 0.7], tam=11, destaque=2)
topicos(s, 7.2, 4.0, 5.55, [
    ("Quem e quando.", "Localização e histórico dizem quem é vulnerável (0,091 e 0,071 somados por grupo); o clima da "
                       "estação diz quando (0,055). O clima antes das chuvas não ajuda (−0,006)."),
    ("Atenção ao peso da localização.", "Parte do aprendido é “nesta região costuma quebrar”, o que ajuda a explicar o "
                                        "desempenho desigual entre estados."),
    ("Antecedência custa.", "Dois terços do ganho vêm dos dois últimos meses de chuva. O aviso confiável sai no fim da "
                            "estação; para antes do plantio, seria preciso previsão climática sazonal."),
], tam=12, espaco=6)
n_pag += 1; rodape(s, "Variáveis de clima são correlacionadas entre si, e a permutação tende a subestimar cada uma isoladamente.", n_pag)

# ------------------------------------------------------- A9 equidade e limites
s = novo(notas="Equidade: o mesmo limiar atende grupos de forma desigual. E os limites do que se pode afirmar.")
titulo(s, "Equidade entre grupos e limites estatísticos")
tabela(s, 0.6, 1.5, 6.4, 4.75, ["Grupo (teste)", "Lavouras", "Quebras", "Recall", "Precisão"], EQUIDADE,
       larguras=[2.7, 0.95, 0.9, 0.9, 0.95], tam=12)
texto(s, 0.6, 6.35, 6.4, 0.55, "Ceará e Bahia tiveram taxas de quebra parecidas, mas o modelo avisou 30% das quebras "
                               "cearenses e 77% das baianas.", tam=12, cor=TINTA2)
texto(s, 7.4, 1.5, 5.35, 0.35, "O QUE OS NÚMEROS NÃO PERMITEM AFIRMAR", tam=12, negrito=True, cor=VERDE)
topicos(s, 7.4, 1.95, 5.35, [
    ("Sem intervalos de confiança.", "Lavouras vizinhas no mesmo ano são correlacionadas; o tamanho efetivo da amostra "
                                     "é bem menor que 17 mil."),
    ("Poucos anos independentes.", "Seis safras no teste e dez na validação. Um ano atípico muda as métricas."),
    ("Alvo com ruído.", "O rendimento municipal é estimado por agentes do IBGE e mistura sequeiro com irrigação."),
    ("Resolução.", "Clima mensal em grade de 50 km não vê veranicos nem chuvas localizadas."),
    ("Calendário fixo.", "A estação chuvosa foi definida com a média até 2019 e não se adapta a anos de chuva atrasada."),
    ("Antes de operar:", "limiar por região, acompanhamento do recall por grupo e recalibração a cada safra."),
], tam=12, espaco=6)
n_pag += 1; rodape(s, "Estados com menos de 250 quebras no teste foram omitidos da tabela. Quartis pela área plantada no ano anterior.", n_pag)

# ------------------------------------------------------ A10 safra atual e chuva
s = novo(notas="Como a safra de 2026 é prevista e como a chuva recente é calculada, e por que as duas coisas não se misturam.")
titulo(s, f"Safra de {ANO_ATUAL} e chuva recente: como são calculadas")
texto(s, 0.6, 1.5, 6.3, 0.35, f"PREVISÃO DA SAFRA DE {ANO_ATUAL}", tam=12, negrito=True, cor=VERDE)
topicos(s, 0.6, 1.9, 6.3, [
    ("1. Conferência.", "O script refaz as variáveis fora do notebook, treina com 2003–2019 e compara as 17.310 "
                        "probabilidades do teste: maior diferença de 0,00005."),
    ("2. Limiar.", "Sete blocos fora da amostra, de 2012 a 2025, com a mesma regra de 75% de recall: τ = 0,472."),
    ("3. Calibração.", "Curva de Platt ajustada nas mesmas previsões fora da amostra. Em probabilidade, o alerta sai "
                       f"a partir de {atual.loc[atual['alerta'] == 1, 'prob_quebra'].min():.0%}."),
    ("4. Reajuste.", f"Mesmos hiperparâmetros, todas as safras conhecidas (2003–2025). {milhar(len(atual))} lavouras "
                     f"previstas, {pct_alto_atual:.0%} em risco alto."),
], tam=12, espaco=5)
tabela(s, 0.6, 4.35, 6.3, 2.45, ["Bloco fora da amostra", "Quebras avisadas", "Alertas confirmados"], BLOCOS_2026,
       larguras=[2.3, 2.0, 2.0], tam=11)
texto(s, 7.3, 1.5, 5.45, 0.35, "CHUVA RECENTE (NASA POWER, DIÁRIO)", tam=12, negrito=True, cor=VERDE)
formula(s, 7.3, 1.9, 5.45, 1.7, [
    "normal = Σ_d  P̄[mês(d)] / dias(mês(d))",
    "% do normal = 100 · chuva(90 dias) / normal",
    [("d: cada dia da janela. O normal mensal é rateado pelos dias", {"tam": 12, "cor": TINTA2})],
], tam=15)
topicos(s, 7.3, 3.8, 5.45, [
    ("Classes do mapa.", "Menos de 50% (muito abaixo), 50–80% (abaixo), 80–120% (normal), mais de 120% (acima)."),
    ("Época seca.", "Normal menor que 0,55 mm por dia: não se compara, porque dividir por quase zero não faz sentido."),
    ("Dias sem chuva.", "Dias seguidos com menos de 1 mm, até a última medição."),
    ("Por que não entra no modelo.", "Os dias recentes vêm de um produto preliminar. No ponto de teste, a umidade do "
                                     "solo caiu de 0,57 para 0,35 na troca de produto: uma descontinuidade que não é física."),
], tam=12, espaco=5)
n_pag += 1; rodape(s, f"A previsão de {ANO_ATUAL} só poderá ser conferida quando o IBGE publicar o resultado, em {ANO_ATUAL + 1}. Chuva medida até {CHUVA_ATE}.", n_pag)

# ------------------------------------------------------- A11 arquitetura técnica
s = novo(notas="Arquitetura técnica: o que roda fora de linha, o que o servidor faz e o que fica no navegador.")
titulo(s, "Arquitetura técnica da plataforma")
colunas_arq = [
    ("Fora de linha (scripts Python)", FUNDO, TINTA, TINTA2, [
        ("coletar_dados.py", "API SIDRA e NASA POWER, com cache e novas tentativas"),
        ("Notebook de ML", "pandas e scikit-learn: variáveis, validação, modelos, calibração"),
        ("atualizar_clima.py", "clima consolidado do ano corrente"),
        ("prever_safra_atual.py", "conferência com o notebook, limiar, calibração e previsão"),
        ("preparar_app.py", "gera os CSVs que a plataforma lê"),
    ]),
    ("Servidor (FastAPI + Uvicorn)", VERDE_ESC, BRANCO, VERDE_CLARO, [
        ("dados.py", "CSVs (3 MB) carregados uma vez em memória; consultas são filtros sobre listas"),
        ("clima.py", "chuva diária da NASA: 6 conexões, gravação atômica, trava, atualização a cada 12 h"),
        ("chat.py", "assistente por regras: entidades, 11 intenções e contexto"),
        ("auth.py", "PBKDF2-HMAC-SHA256 (200 mil iterações); cookie assinado com HMAC, 8 horas"),
        ("API REST em JSON", "risco, município, análises, chuva, chat e exportação em CSV"),
    ]),
    ("Navegador (HTML, CSS e JavaScript)", FUNDO, TINTA, TINTA2, [
        ("Módulos nativos, sem build", "cada página é carregada sob demanda; navegação por hash"),
        ("Leaflet 1.9 (canvas)", "1.400 pontos com fluidez; dois modos de mapa"),
        ("Chart.js 4.5", "gráficos com filtro cruzado por estado"),
        ("Simulador de limiar", "histograma em 100 faixas; recall e precisão por soma acumulada, sem nova chamada"),
        ("Preferências", "filtros compartilhados, tema claro ou escuro e tamanho do texto"),
    ]),
]
x = 0.6
for i, (cab, fundo_c, cor_t, cor_d, itens) in enumerate(colunas_arq):
    cartao(s, x, 1.5, 3.9, 4.55, fundo_c)
    texto(s, x + 0.25, 1.65, 3.4, 0.4, cab, tam=15, negrito=True, cor=cor_t)
    texto(s, x + 0.25, 2.15, 3.4, 3.8, [[(a + ": ", {"negrito": True, "cor": cor_t}), (b, {"cor": cor_d})] for a, b in itens],
          tam=12, espaco=7)
    if i < 2:
        seta(s, x + 3.93, 3.75, x + 4.17, 3.75)
    x += 4.125
topicos(s, 0.6, 6.2, 12.15, [
    ("Decisões de engenharia:", "o servidor não treina nem carrega o modelo (as previsões chegam prontas dos scripts); não há "
     "banco de dados; se a NASA estiver fora do ar, a chuva anterior é mantida; e a chuva recente nunca alimenta o risco."),
], tam=12)
n_pag += 1; rodape(s, "Dependências do servidor: FastAPI e Uvicorn. Tudo o mais usa a biblioteca padrão do Python.", n_pag)

# =========================================================== 14 encerramento
s = novo(VERDE_ESC, "Fechamento: repetir a ideia central e convidar a assistir ao vídeo.")
marca(s, 0.75, 0.8, 1.5)
texto(s, 0.75, 2.0, 11.5, 1.6, "Os satélites já veem a seca chegar.\nO Safra Sentinela faz o aviso chegar a quem planta.",
      tam=36, negrito=True, cor=BRANCO, nome="Título")
cartao(s, 0.75, 4.35, 11.8, 1.5, "1F3A2B")
texto(s, 1.05, 4.52, 11.2, 0.35, "VÍDEO PITCH", tam=12, negrito=True, cor=AMBAR)
texto(s, 1.05, 4.95, 11.2, 0.6, LINK_VIDEO, tam=22, cor=BRANCO)
texto(s, 0.75, 6.35, 11.5, 0.6, "Safra Sentinela · Grupo RHEAL · Turma 2TSCOA · Global Solution 2026/2 — CitizenTech",
      tam=14, cor=VERDE_CLARO)

SAIDA.parent.mkdir(exist_ok=True)
prs.save(SAIDA)
print("salvo:", SAIDA, "|", len(prs.slides), "slides")
