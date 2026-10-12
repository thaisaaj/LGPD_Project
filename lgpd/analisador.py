"""Orquestra o fluxo completo: coleta -> extração -> motor de regras -> IA -> histórico."""

import json
import re
import time
from datetime import datetime
from pathlib import Path

from . import agente_ia, coletor, extrator, regras

PASTA_HISTORICO = Path(__file__).resolve().parent.parent / "dados" / "historico"


def analisar_url(url: str, finalidade: str | None = None, usar_ia: bool = True, usar_navegador: bool = True) -> dict:
    etapas = {}
    t = time.time()
    coleta = coletor.coletar(url, usar_navegador=usar_navegador)
    etapas["coleta"] = round(time.time() - t, 2)

    t = time.time()
    extracao = extrator.extrair(coleta)
    texto_politica = None
    if extracao["links"]["privacidade"]:
        texto_politica = coletor.baixar_texto(extracao["links"]["privacidade"])
    etapas["extracao"] = round(time.time() - t, 2)

    t = time.time()
    resultado = regras.analisar(coleta, extracao, texto_politica, finalidade or None)
    etapas["regras"] = round(time.time() - t, 2)

    t = time.time()
    ia = agente_ia.analisar(coleta["url_final"], extracao, resultado, texto_politica) if usar_ia else \
        {"disponivel": False, "motivo": "Análise por IA desativada nesta execução."}
    etapas["ia"] = round(time.time() - t, 2)

    # mescla a opinião da IA na tabela de campos (por rótulo)
    if ia.get("disponivel"):
        por_rotulo = {a["campo"].strip().lower(): a for a in ia.get("avaliacao_campos", [])}
        for c in resultado["campos"]:
            a = por_rotulo.get((c["rotulo"] or c["nome"] or c["id"]).strip().lower())
            if a:
                c["avaliacao_ia"] = a["necessidade"]
                c["justificativa_ia"] = a["justificativa"]

    relatorio = {
        "id": datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^a-z0-9]+", "-", extracao["host"].lower())[:40],
        "data": datetime.now().isoformat(timespec="seconds"),
        "url": coleta["url_final"],
        "titulo": extracao["titulo"],
        "coleta": {
            "metodo": coleta["metodo"], "status_http": coleta["status"], "aviso": coleta.get("aviso"),
            "tempo_s": coleta["tempo_coleta_s"], "politica_analisada": bool(texto_politica),
        },
        "links": extracao["links"],
        "banner_cookies": extracao["banner_cookies"],
        "cmp": extracao["cmp"],
        "dominios_terceiros": extracao["dominios_terceiros"],
        **resultado,
        "ia": ia,
        "tempos_etapas_s": etapas,
    }
    salvar(relatorio)
    return relatorio


def salvar(relatorio: dict) -> None:
    PASTA_HISTORICO.mkdir(parents=True, exist_ok=True)
    (PASTA_HISTORICO / f"{relatorio['id']}.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")


def listar_historico(limite: int = 30) -> list[dict]:
    if not PASTA_HISTORICO.exists():
        return []
    itens = []
    for p in sorted(PASTA_HISTORICO.glob("*.json"), reverse=True)[:limite]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            itens.append({"id": d["id"], "url": d["url"], "data": d["data"], "score": d["score"], "nivel": d["nivel"],
                          "ia": bool(d.get("ia", {}).get("disponivel"))})
        except (json.JSONDecodeError, KeyError):
            continue
    return itens


def carregar(id_: str) -> dict | None:
    if not re.fullmatch(r"[\w-]+", id_):
        return None
    p = PASTA_HISTORICO / f"{id_}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
