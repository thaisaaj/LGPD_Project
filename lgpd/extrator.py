"""
Etapa 2b - Extração estruturada a partir do HTML coletado.

Produz: formulários e seus campos (com rótulos e texto próximo), links
relevantes (política de privacidade, termos, cookies), banner de cookies e
seus botões, scripts/rastreadores de terceiros e o texto visível da página.
"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .catalogo import (AUTOCOMPLETE, CMPS, RASTREADORES, TIPO_INPUT, TIPOS_DADOS,
                       TIPOS_POR_ID, normalizar)
from .coletor import absoluta, eh_terceiro

TIPOS_IGNORADOS = {"hidden", "submit", "button", "reset", "image", "search"}
NOMES_BUSCA = re.compile(r"^(q|s|busca|search|pesquisa|query|termo)$", re.I)

RE_LINK_PRIVACIDADE = re.compile(r"privacidade|privacy|protecao de dados|lgpd|dados pessoais", re.I)
RE_LINK_TERMOS = re.compile(r"termos|terms|condicoes de uso", re.I)
RE_LINK_COOKIES = re.compile(r"politica de cookies|cookie policy|aviso de cookies|cookies", re.I)

RE_BANNER = re.compile(r"cookie|consent|lgpd|gdpr|privacy-banner|cc-window|cmp|onetrust|adopt", re.I)
RE_BTN_ACEITAR = re.compile(r"aceit|accept|concord|permitir|allow|entendi|\bok\b|prosseguir|continuar", re.I)
RE_BTN_RECUSAR = re.compile(r"recus|rejeit|reject|declin|negar|nao aceito|apenas (os )?(necessarios|essenciais)|somente (os )?(necessarios|essenciais)|only necessary|deny", re.I)
RE_BTN_CONFIG = re.compile(r"configur|personaliz|preferenc|gerenciar|manage|ajustes|settings|opcoes", re.I)


def _texto(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def _rotulo(soup, campo) -> str:
    """Descobre o rótulo humano de um campo usando várias heurísticas."""
    cid = campo.get("id")
    if cid:
        lab = soup.find("label", attrs={"for": cid})
        if lab and _texto(lab):
            return _texto(lab)
    pai = campo.find_parent("label")
    if pai and _texto(pai):
        return _texto(pai)
    if campo.get("aria-label"):
        return campo["aria-label"].strip()
    if campo.get("aria-labelledby"):
        alvo = soup.find(id=campo["aria-labelledby"].split()[0])
        if alvo:
            return _texto(alvo)
    # checkbox costuma ter o texto logo depois (ex.: <input type=checkbox> Aceito os termos)
    if (campo.get("type") or "").lower() in ("checkbox", "radio"):
        prox = campo.find_next(string=lambda s: s and s.strip())
        if prox and prox.find_parent(["script", "style"]) is None:
            bloco = prox.find_parent(["label", "span", "p", "div"])
            return _texto(bloco) if bloco and len(_texto(bloco)) <= 300 else prox.strip()
    # texto imediatamente anterior (ex.: <span>CPF</span><input>)
    ant = campo.find_previous(string=lambda s: s and s.strip())
    if ant and len(ant.strip()) < 60 and ant.find_parent(["script", "style"]) is None:
        return ant.strip()
    return campo.get("placeholder") or campo.get("title") or ""


def classificar_campo(campo: dict) -> tuple[str, str]:
    """Retorna (tipo_id, evidência) usando autocomplete, type e regex nos textos."""
    ac = (campo.get("autocomplete") or "").lower().split()
    for token in ac:
        if token in AUTOCOMPLETE:
            return AUTOCOMPLETE[token], f'autocomplete="{token}"'

    texto = normalizar(" ".join(filter(None, [
        campo.get("rotulo"), campo.get("nome"), campo.get("id"), campo.get("placeholder")])))

    if campo["tipo_html"] == "checkbox":
        if re.search(TIPOS_POR_ID["consentimento"]["padrao"], texto):
            return "consentimento", "checkbox com texto de aceite"

    for tipo in TIPOS_DADOS:
        if tipo["id"] == "consentimento":
            continue
        if re.search(tipo["padrao"], texto):
            return tipo["id"], f"texto: “{texto[:60]}”"

    if campo["tipo_html"] in TIPO_INPUT:
        t = TIPO_INPUT[campo["tipo_html"]]
        return t, f'type="{campo["tipo_html"]}"'
    if campo["tipo_html"] == "textarea":
        return "mensagem", "textarea"
    return "desconhecido", "sem correspondência"


def _extrair_campos(soup, raiz) -> list[dict]:
    campos = []
    vistos_radio = set()
    for el in raiz.find_all(["input", "select", "textarea"]):
        tipo_html = (el.get("type") or el.name).lower() if el.name == "input" else el.name
        if tipo_html in TIPOS_IGNORADOS:
            continue
        nome = el.get("name") or ""
        if NOMES_BUSCA.match(nome) or (el.get("role") == "searchbox"):
            continue
        if tipo_html == "radio":
            if nome in vistos_radio:
                continue
            vistos_radio.add(nome)
        campo = {
            "nome": nome,
            "id": el.get("id") or "",
            "tipo_html": tipo_html,
            "placeholder": el.get("placeholder") or "",
            "autocomplete": el.get("autocomplete") or "",
            "obrigatorio": el.has_attr("required") or el.get("aria-required") == "true",
            "marcado": el.has_attr("checked"),
            "rotulo": _rotulo(soup, el)[:300],
        }
        if tipo_html == "radio":
            # para radios, o "rótulo" útil costuma ser a pergunta do grupo (fieldset/legend)
            fs = el.find_parent("fieldset")
            if fs and fs.find("legend"):
                campo["rotulo"] = _texto(fs.find("legend"))[:150]
            elif nome:
                campo["rotulo"] = nome
        if el.name == "select":
            campo["opcoes"] = [_texto(o)[:40] for o in el.find_all("option")][:12]
        # asterisco no rótulo também indica obrigatoriedade
        if "*" in campo["rotulo"]:
            campo["obrigatorio"] = True
            campo["rotulo"] = campo["rotulo"].replace("*", "").strip()
        campo["tipo_dado"], campo["evidencia"] = classificar_campo(campo)
        campos.append(campo)
    return campos


def extrair(coleta: dict) -> dict:
    url = coleta["url_final"]
    host = urlparse(url).hostname or ""
    soup = BeautifulSoup(coleta["html"], "html.parser")

    titulo = _texto(soup.title)
    h1 = _texto(soup.find("h1"))

    # ---------------- scripts e rastreadores ----------------
    urls_recursos = [r["url"] for r in coleta.get("requisicoes", [])]
    for tag, attr in (("script", "src"), ("img", "src"), ("iframe", "src"), ("link", "href")):
        for el in soup.find_all(tag):
            if el.get(attr):
                urls_recursos.append(absoluta(url, el[attr]))
    scripts_inline = " ".join(s.get_text() for s in soup.find_all("script") if not s.get("src"))

    dominios_terceiros = sorted({urlparse(u).hostname for u in urls_recursos
                                 if urlparse(u).hostname and eh_terceiro(urlparse(u).hostname, host)})
    rastreadores = {}
    for u in urls_recursos + [scripts_inline]:
        for chave, nome in RASTREADORES.items():
            if chave in u:
                rastreadores.setdefault(nome, chave)
    # gtag/fbq inline também indicam rastreamento
    if re.search(r"\bfbq\(", scripts_inline):
        rastreadores.setdefault("Meta Pixel", "fbq()")
    if re.search(r"\bgtag\(|googletagmanager", scripts_inline):
        rastreadores.setdefault("Google Tag Manager / gtag", "gtag()")

    cmp = None
    for chave, nome in CMPS.items():
        if any(chave in u.lower() for u in urls_recursos) or chave in scripts_inline.lower():
            cmp = nome
            break

    conteudo_misto = [u for u in urls_recursos if url.startswith("https://") and u.startswith("http://")]

    # ---------------- texto visível ----------------
    for t in soup(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    texto_pagina = _texto(soup.body or soup)

    # ---------------- links relevantes ----------------
    links = {"privacidade": None, "termos": None, "cookies": None}
    links_texto = {}
    for a in soup.find_all("a", href=True):
        rot = normalizar(_texto(a) + " " + a.get("href", "") + " " + (a.get("title") or ""))
        href = absoluta(url, a["href"])
        if href.startswith(("javascript:", "mailto:")):
            continue
        if not links["cookies"] and re.search(r"politica de cookies|cookie policy|aviso de cookies", rot):
            tipo = "cookies"
        elif not links["privacidade"] and RE_LINK_PRIVACIDADE.search(rot):
            tipo = "privacidade"
        elif not links["termos"] and RE_LINK_TERMOS.search(rot):
            tipo = "termos"
        else:
            continue
        links[tipo] = href
        links_texto[tipo] = _texto(a)[:80]

    # ---------------- banner de cookies ----------------
    banner = None
    candidatos = []
    for el in soup.find_all(["div", "section", "aside", "dialog", "footer", "form"]):
        marca = " ".join([el.get("id") or ""] + (el.get("class") or []) + [el.get("aria-label") or ""])
        txt = _texto(el)
        if not txt or len(txt) > 1500:
            continue
        if (RE_BANNER.search(marca) and "cookie" in normalizar(txt)) or \
           (re.search(r"cookies?", normalizar(txt)) and el.find(["button", "a"]) and len(txt) < 700
                and re.search(r"utilizamos|usamos|este site|nosso site|experiencia|navegacao", normalizar(txt))):
            candidatos.append(el)
    if candidatos:
        el = min(candidatos, key=lambda e: len(_texto(e)))  # o mais específico
        botoes = [normalizar(_texto(b) or b.get("aria-label") or b.get("value") or "")
                  for b in el.find_all(["button", "a", "input"])]
        botoes = [b for b in botoes if b]
        banner = {
            "texto": _texto(el)[:400],
            "botoes": botoes[:10],
            "aceitar": any(RE_BTN_ACEITAR.search(b) for b in botoes),
            "recusar": any(RE_BTN_RECUSAR.search(b) for b in botoes),
            "configurar": any(RE_BTN_CONFIG.search(b) for b in botoes),
        }

    # ---------------- formulários e campos ----------------
    soup_forms = BeautifulSoup(coleta["html"], "html.parser")  # cópia com estrutura completa
    formularios = []
    for i, f in enumerate(soup_forms.find_all("form")):
        campos = _extrair_campos(soup_forms, f)
        if not campos:
            continue
        botao = f.find(lambda t: t.name == "button" or (t.name == "input" and t.get("type") in ("submit", "button")))
        action = absoluta(url, f.get("action") or url)
        formularios.append({
            "indice": i,
            "id": f.get("id") or f.get("name") or f"form-{i + 1}",
            "action": action,
            "metodo": (f.get("method") or "get").lower(),
            "action_terceiro": eh_terceiro(urlparse(action).hostname or host, host),
            "texto_botao": _texto(botao) or (botao.get("value") if botao else ""),
            "texto": _texto(f)[:3000],
            "links": [{"texto": _texto(a), "href": absoluta(url, a["href"])} for a in f.find_all("a", href=True)][:20],
            "campos": campos,
        })
    # campos soltos (fora de <form>, comuns em SPAs)
    soltos = [c for c in _extrair_campos(soup_forms, soup_forms)
              if not any(c["nome"] == x["nome"] and c["id"] == x["id"] for fm in formularios for x in fm["campos"])]
    if soltos:
        formularios.append({
            "indice": len(formularios), "id": "campos-fora-de-form", "action": url, "metodo": "js",
            "action_terceiro": False, "texto_botao": "", "texto": texto_pagina[:3000], "links": [],
            "campos": soltos,
        })

    return {
        "host": host,
        "titulo": titulo,
        "h1": h1,
        "texto_pagina": texto_pagina,
        "links": links,
        "links_texto": links_texto,
        "banner_cookies": banner,
        "cmp": cmp,
        "rastreadores": [{"nome": n, "evidencia": e} for n, e in rastreadores.items()],
        "dominios_terceiros": dominios_terceiros,
        "conteudo_misto": conteudo_misto[:20],
        "formularios": formularios,
    }
