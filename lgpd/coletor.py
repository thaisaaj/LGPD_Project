"""
Etapa 2 - Coleta da página.

Tenta primeiro com um navegador headless (Playwright/Chromium), que executa
JavaScript e permite capturar cookies e requisições a terceiros. Se o
Playwright não estiver disponível, cai para uma coleta simples via requests.
"""

import time
from urllib.parse import urlparse, urljoin

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 LGPD-Web-Analyzer/1.0")

SUFIXOS_COMPOSTOS = {"com.br", "gov.br", "org.br", "net.br", "edu.br", "co.uk", "com.au", "jus.br", "leg.br", "mp.br"}


def dominio_base(host: str) -> str:
    """Aproxima o domínio registrável (ex.: loja.exemplo.com.br -> exemplo.com.br)."""
    host = (host or "").lower().lstrip(".").split(":")[0]
    partes = host.split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in SUFIXOS_COMPOSTOS:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:]) if len(partes) >= 2 else host


def eh_terceiro(host: str, site: str) -> bool:
    return dominio_base(host) != dominio_base(site)


def validar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("Informe uma URL.")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("URL inválida.")
    return url


def _coletar_playwright(url: str, timeout: int) -> dict:
    from playwright.sync_api import sync_playwright

    requisicoes = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=UA, locale="pt-BR")
            page = ctx.new_page()
            page.on("request", lambda r: requisicoes.append({"url": r.url, "tipo": r.resource_type}))
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(1500)  # tempo para banners de cookies aparecerem
            html = page.content()
            cookies = ctx.cookies()
            headers = {k.lower(): v for k, v in (resp.all_headers() if resp else {}).items()}
            return {
                "metodo": "navegador (Playwright)",
                "url_final": page.url,
                "status": resp.status if resp else None,
                "html": html,
                "headers": headers,
                "cookies": [
                    {"nome": c["name"], "dominio": c["domain"], "expira": c.get("expires", -1),
                     "secure": c.get("secure", False), "httponly": c.get("httpOnly", False),
                     "samesite": c.get("sameSite")}
                    for c in cookies
                ],
                "requisicoes": requisicoes,
            }
        finally:
            browser.close()


def _coletar_requests(url: str, timeout: int) -> dict:
    s = requests.Session()
    r = s.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"}, timeout=timeout)
    cookies = [
        {"nome": c.name, "dominio": c.domain, "expira": c.expires if c.expires else -1,
         "secure": c.secure, "httponly": c.has_nonstandard_attr("HttpOnly"), "samesite": None}
        for c in s.cookies
    ]
    return {
        "metodo": "requisição HTTP simples (sem JavaScript)",
        "url_final": r.url,
        "status": r.status_code,
        "html": r.text,
        "headers": {k.lower(): v for k, v in r.headers.items()},
        "cookies": cookies,
        "requisicoes": [],  # preenchido depois a partir das tags <script>/<img>
    }


def coletar(url: str, timeout: int = 30, usar_navegador: bool = True) -> dict:
    url = validar_url(url)
    inicio = time.time()
    erro_navegador = None
    dados = None
    if usar_navegador:
        try:
            dados = _coletar_playwright(url, timeout)
        except Exception as e:  # Playwright ausente, navegador não instalado, timeout...
            erro_navegador = str(e).splitlines()[0][:200]
    if dados is None:
        dados = _coletar_requests(url, timeout)
        if erro_navegador:
            dados["aviso"] = f"Navegador headless indisponível ({erro_navegador}); usada coleta simples."
    dados["url_solicitada"] = url
    dados["tempo_coleta_s"] = round(time.time() - inicio, 2)
    return dados


def baixar_texto(url: str, timeout: int = 15) -> str | None:
    """Baixa uma página auxiliar (ex.: política de privacidade) e devolve o texto visível."""
    from bs4 import BeautifulSoup
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"}, timeout=timeout)
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        return soup.get_text(" ", strip=True)
    except Exception:
        return None


def absoluta(base: str, href: str) -> str:
    return urljoin(base, href)
