"""Login da plataforma: usuários em arquivo JSON, senhas com PBKDF2 e sessão em cookie assinado.

É um controle de acesso de demonstração acadêmica, não um sistema de identidade completo.

Gerenciar usuários pela linha de comando:
    python -m app.auth adicionar <email> "<nome>" <senha> [papel]
    python -m app.auth listar
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

ARQUIVO = Path(os.getenv("SAFRA_USUARIOS", Path(__file__).resolve().parent / "usuarios.json"))
COOKIE = "safra_sessao"
DURACAO = 8 * 3600  # segundos
ITERACOES = 200_000
# Sem SAFRA_SECRET, a chave muda a cada reinício e as sessões abertas expiram junto.
SEGREDO = (os.getenv("SAFRA_SECRET") or secrets.token_hex(32)).encode()

VISITANTE = {"email": "visitante", "nome": "Visitante", "papel": "Visitante"}


def _usuarios() -> Dict[str, Dict[str, str]]:
    if not ARQUIVO.exists():
        return {}
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def _hash(senha: str, sal: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, ITERACOES).hex()


def adicionar(email: str, nome: str, senha: str, papel: str = "Integrante") -> None:
    usuarios = _usuarios()
    sal = secrets.token_bytes(16)
    usuarios[email.strip().lower()] = {"nome": nome, "papel": papel, "sal": sal.hex(),
                                       "hash": _hash(senha, sal)}
    ARQUIVO.write_text(json.dumps(usuarios, ensure_ascii=False, indent=2), encoding="utf-8")


def verificar(email: str, senha: str) -> Optional[Dict[str, str]]:
    registro = _usuarios().get(email.strip().lower())
    if not registro:
        _hash(senha, b"0" * 16)  # mesmo custo quando o e-mail não existe
        return None
    if not hmac.compare_digest(_hash(senha, bytes.fromhex(registro["sal"])), registro["hash"]):
        return None
    return {"email": email.strip().lower(), "nome": registro["nome"], "papel": registro["papel"]}


def criar_token(usuario: Dict[str, str]) -> str:
    corpo = base64.urlsafe_b64encode(json.dumps({**usuario, "exp": int(time.time()) + DURACAO}).encode()).decode()
    assinatura = hmac.new(SEGREDO, corpo.encode(), hashlib.sha256).hexdigest()
    return f"{corpo}.{assinatura}"


def ler_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token or "." not in token:
        return None
    corpo, assinatura = token.rsplit(".", 1)
    esperado = hmac.new(SEGREDO, corpo.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(assinatura, esperado):
        return None
    try:
        dados = json.loads(base64.urlsafe_b64decode(corpo.encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    if dados.get("exp", 0) < time.time():
        return None
    return {k: dados.get(k) for k in ("email", "nome", "papel")}


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "adicionar":
        adicionar(sys.argv[2], sys.argv[3], sys.argv[4], *(sys.argv[5:6]))
        print("usuário salvo:", sys.argv[2].lower())
    elif len(sys.argv) == 2 and sys.argv[1] == "listar":
        for email, u in _usuarios().items():
            print(f"{email}  —  {u['nome']} ({u['papel']})")
    else:
        print(__doc__)
