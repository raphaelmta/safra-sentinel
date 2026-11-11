"""Previsão da safra atual, que ainda não tem resultado oficial do IBGE.

Passos:
  1. Confere que este script reproduz o notebook: treina com 2003–2019 e compara as probabilidades
     de 2020–2025 com notebook/previsoes_teste.csv.
  2. Escolhe o limiar de alerta em previsões fora da amostra (blocos de anos, janela expansiva),
     para avisar 75% das quebras — a mesma regra do notebook, agora com os anos até 2025.
  3. Calibra a pontuação (Platt) com as mesmas previsões fora da amostra, para que a chance de
     quebra informada seja uma probabilidade.
  4. Reajusta o modelo com todas as safras conhecidas (2003–2025) e prevê a safra atual.

Uso: python scripts/prever_safra_atual.py [ano]      (padrão: ano corrente)
Saída: data/previsoes_safra_<ano>.csv
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, precision_recall_curve, precision_score, recall_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo import PREDITORAS, CalibradorPlatt, criar_modelo, erro_calibracao, montar_base  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
RECALL_ALVO = 0.75
BLOCOS = [(2012, 2013), (2014, 2015), (2016, 2017), (2018, 2019), (2020, 2021), (2022, 2023), (2024, 2025)]


def limiar_para_recall(y, prob, alvo=RECALL_ALVO) -> float:
    _, recall, limiares = precision_recall_curve(y, prob)
    return float(limiares[np.where(recall[:-1] >= alvo)[0][-1]])


def main() -> None:
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    municipios = pd.read_csv(DATA / "municipios_semiarido.csv")
    producao = pd.read_csv(DATA / "producao_pam.csv")
    clima = pd.read_csv(DATA / "clima_mensal.csv")
    arq_recente = DATA / f"clima_mensal_{ano}.csv"
    if not arq_recente.exists():
        sys.exit(f"Falta {arq_recente}. Rode antes: python scripts/atualizar_clima.py {ano}")
    recente = pd.read_csv(arq_recente)
    if ano - 1 != producao["ano"].max():
        sys.exit(f"A produção vai até {producao['ano'].max()}; só é possível prever {producao['ano'].max() + 1}.")

    # 1. reprodução do notebook
    base_nb = montar_base(municipios, producao, clima)
    treino_nb, teste_nb = base_nb[base_nb["ano"] <= 2019], base_nb[base_nb["ano"] > 2019]
    prob_nb = criar_modelo().fit(treino_nb[PREDITORAS], treino_nb["quebra"]).predict_proba(teste_nb[PREDITORAS])[:, 1]
    ref = pd.read_csv(RAIZ / "notebook" / "previsoes_teste.csv")
    coluna = "pontuacao" if "pontuacao" in ref.columns else "prob_quebra"   # saída bruta do modelo
    conf = (teste_nb[["cod_mun", "ano", "cultura"]].assign(prob=prob_nb)
            .merge(ref[["cod_mun", "ano", "cultura", coluna]], on=["cod_mun", "ano", "cultura"]))
    diferenca = float((conf["prob"] - conf[coluna]).abs().max())
    print(f"1. Conferência com o notebook: {len(conf):,} previsões, maior diferença = {diferenca:.5f}")
    if len(conf) != len(ref) or diferenca > 1e-3:
        sys.exit("   As previsões não batem com o notebook. Revise scripts/modelo.py antes de continuar.")

    # 2. limiar com previsões fora da amostra
    base = montar_base(municipios, producao, pd.concat([clima, recente], ignore_index=True), ano_previsao=ano)
    conhecida = base[base["ano"] < ano].reset_index(drop=True)
    atual = base[base["ano"] == ano].reset_index(drop=True)
    anos = conhecida["ano"].to_numpy()
    fora, real, bloco_de = [], [], []
    for ini, fim in BLOCOS:
        tr, va = anos < ini, (anos >= ini) & (anos <= fim)
        m = criar_modelo().fit(conhecida.loc[tr, PREDITORAS], conhecida.loc[tr, "quebra"])
        fora.append(m.predict_proba(conhecida.loc[va, PREDITORAS])[:, 1])
        real.append(conhecida.loc[va, "quebra"].to_numpy())
        bloco_de += [f"{ini}–{fim}"] * int(va.sum())
    fora, real = np.concatenate(fora), np.concatenate(real).astype(int)
    limiar = limiar_para_recall(real, fora)
    print(f"2. Limiar de alerta: {limiar:.3f} (recall de {RECALL_ALVO:.0%} fora da amostra, 2012–2025)")
    aval = pd.DataFrame({"bloco": bloco_de, "real": real, "alerta": (fora >= limiar).astype(int)})
    for bloco, g in aval.groupby("bloco"):
        print(f"   {bloco}: quebras avisadas {recall_score(g['real'], g['alerta']):.0%}, "
              f"alertas confirmados {precision_score(g['real'], g['alerta']):.0%}, "
              f"lavouras alertadas {g['alerta'].mean():.0%}")

    # 3. calibração da pontuação em probabilidade
    blocos = np.array(bloco_de)
    ordem = [f"{i}–{f}" for i, f in BLOCOS]
    print("3. Calibração de Platt, validada para a frente (calibra nos blocos anteriores, avalia no bloco):")
    for k in range(2, len(ordem)):
        antes, este = np.isin(blocos, ordem[:k]), blocos == ordem[k]
        p = CalibradorPlatt().fit(fora[antes], real[antes])(fora[este])
        print(f"   {ordem[k]}: prevista {p.mean():.0%}, real {real[este].mean():.0%} | "
              f"Brier {brier_score_loss(real[este], fora[este]):.3f} → {brier_score_loss(real[este], p):.3f} | "
              f"ECE {erro_calibracao(real[este], fora[este]):.3f} → {erro_calibracao(real[este], p):.3f}")
    calibrar = CalibradorPlatt().fit(fora, real)
    limiar_prob = float(calibrar([limiar])[0])
    print(f"   ajuste final (2012–2025): p = sigmoide({calibrar.a:.3f} × logit(s) + ({calibrar.b:.3f})); "
          f"o limiar {limiar:.3f} equivale a {limiar_prob:.1%} de probabilidade")

    # 4. modelo final e previsão da safra atual
    faltando = atual[[c for c in PREDITORAS if c.startswith("chuva_mm_m")]].isna().any(axis=1).mean()
    if faltando > 0.02:
        sys.exit(f"   {faltando:.0%} das lavouras ainda não têm a estação chuvosa de {ano} completa nos dados.")
    final = criar_modelo().fit(conhecida[PREDITORAS], conhecida["quebra"])
    atual["pontuacao"] = final.predict_proba(atual[PREDITORAS])[:, 1]
    atual["alerta"] = (atual["pontuacao"] >= limiar).astype(int)      # o alerta é decidido na pontuação
    atual["prob_quebra"] = calibrar(atual["pontuacao"])               # o que se mostra é a probabilidade
    saida = (atual[["cod_mun", "municipio", "uf", "latitude", "longitude", "ano", "cultura",
                    "chuva_estacao_pct_normal", "prob_quebra", "alerta"]]
             .assign(quebra_real="", pontuacao=atual["pontuacao"]))
    destino = DATA / f"previsoes_safra_{ano}.csv"
    saida.to_csv(destino, index=False, float_format="%.4f")
    print(f"4. Safra {ano}: {len(saida):,} lavouras previstas, {saida['alerta'].mean():.0%} em risco alto, "
          f"probabilidade média de quebra {saida['prob_quebra'].mean():.0%} "
          f"(chuva média da estação: {saida['chuva_estacao_pct_normal'].mean():.0f}% do normal)")
    print("   por cultura:", saida.groupby("cultura")["alerta"].mean().round(2).to_dict())
    print("   salvo em", destino)


if __name__ == "__main__":
    main()
