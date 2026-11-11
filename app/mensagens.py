"""Texto do aviso enviado ao agricultor, em linguagem simples (WhatsApp e SMS)."""
from __future__ import annotations

import unicodedata
from typing import Any, Dict

from app.dados import NOME_CULTURA


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def montar_mensagens(linha: Dict[str, Any]) -> Dict[str, str]:
    """Recebe uma previsão (município, uf, cultura, nível, chuva_pct) e devolve os dois textos."""
    cultura = NOME_CULTURA.get(linha["cultura"], linha["cultura"])
    local = f"{linha['municipio']}/{linha['uf']}"
    chuva = linha.get("chuva_pct")
    frase_chuva = ""
    if chuva is not None and chuva < 90:
        frase_chuva = f" Choveu menos que o normal: cerca de {chuva}% do esperado para a estação."

    if linha["nivel"] == "alto":
        whatsapp = (
            f"⚠️ *Safra Sentinela — {local}*\n\n"
            f"Risco *ALTO* de perda na lavoura de *{cultura}* este ano.{frase_chuva}\n\n"
            "O que fazer agora:\n"
            "1️⃣ Guarde semente e alimento\n"
            "2️⃣ Procure o técnico ou o sindicato\n"
            "3️⃣ Veja se o seu Garantia-Safra está em dia\n\n"
            "Isto é um aviso de risco, não uma certeza. Responda *1* para ouvir em áudio."
        )
        sms = (f"SAFRA SENTINELA {local}: risco ALTO de perda no {cultura}. Guarde semente, "
               "procure o tecnico e confira o Garantia-Safra.")
    elif linha["nivel"] == "atencao":
        whatsapp = (
            f"🟡 *Safra Sentinela — {local}*\n\n"
            f"*Atenção* com a lavoura de *{cultura}*: o risco de perda está acima do normal.{frase_chuva}\n\n"
            "Acompanhe a chuva das próximas semanas e fale com o técnico se a lavoura sentir.\n\n"
            "Responda *1* para ouvir em áudio."
        )
        sms = (f"SAFRA SENTINELA {local}: ATENCAO com o {cultura}, risco de perda acima do normal. "
               "Acompanhe a chuva e fale com o tecnico.")
    else:
        whatsapp = (
            f"🟢 *Safra Sentinela — {local}*\n\n"
            f"Risco *baixo* de perda na lavoura de *{cultura}* neste momento.\n\n"
            "Seguimos acompanhando e avisamos se algo mudar. Responda *1* para ouvir em áudio."
        )
        sms = f"SAFRA SENTINELA {local}: risco BAIXO de perda no {cultura} neste momento. Avisamos se mudar."
    return {"whatsapp": whatsapp, "sms": _sem_acento(sms)[:160]}
