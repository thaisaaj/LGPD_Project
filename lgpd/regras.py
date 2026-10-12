"""
Etapa 3 - Motor de regras.

Faz verificações objetivas e reprodutíveis (sem IA) sobre os dados extraídos,
cada uma vinculada a um dispositivo da LGPD (Lei 13.709/2018) ou ao Guia
Orientativo de Cookies da ANPD. O resultado de cada regra é:

    ok       -> atende            (1,0 ponto)
    parcial  -> atende em parte   (0,5 ponto)
    falha    -> não atende        (0,0 ponto)
    na       -> não se aplica     (fora do cálculo)

A nota final (0-100) é a média ponderada das categorias, e cada categoria é a
média ponderada das suas regras. Como a nota vem só do motor de regras, ela é
determinística: a mesma página sempre gera a mesma nota.
"""

import re
import time
from collections import Counter
from urllib.parse import urlparse

from .catalogo import (FINALIDADES, PADRAO_FINALIDADE, TIPOS_NEUTROS, TIPOS_POR_ID,
                       TOPICOS_POLITICA, normalizar)
from .coletor import eh_terceiro

PONTOS = {"ok": 1.0, "parcial": 0.5, "falha": 0.0}

CATEGORIAS = {
    "minimizacao":   {"nome": "Minimização de dados", "peso": 25, "base": "Art. 6º, III"},
    "transparencia": {"nome": "Transparência", "peso": 20, "base": "Art. 6º, VI e art. 9º"},
    "consentimento": {"nome": "Consentimento", "peso": 15, "base": "Arts. 7º, 8º e 14"},
    "cookies":       {"nome": "Cookies e rastreamento", "peso": 15, "base": "Guia de Cookies ANPD"},
    "seguranca":     {"nome": "Segurança", "peso": 15, "base": "Art. 46"},
    "direitos":      {"nome": "Direitos do titular e governança", "peso": 10, "base": "Arts. 18 e 41"},
}

IDENTIFICADORES = {"cpf", "rg", "cnh", "passaporte", "titulo_eleitor", "pis"}
RASTREADORES_PUBLICIDADE = {"Google Ads / DoubleClick", "Google Ads", "Google AdSense", "Meta Pixel", "TikTok Pixel",
                            "LinkedIn Ads", "X/Twitter Ads", "Microsoft Ads", "Criteo", "Taboola", "Outbrain",
                            "Pinterest Tag", "Quantcast"}

RE_MARKETING = r"ofertas|promoc|novidades|newsletter|marketing|comunica|parceiros|publicidade|e mails? (promocion|de marketing)|sms|whatsapp"
RE_TERMOS = r"termos|politica|privacidade|condicoes"
RE_CIENCIA = r"ao (clicar|enviar|se cadastrar|cadastrar|continuar|criar|prosseguir|assinar|se inscrever)[^.]{0,120}(concorda|aceita|declara|esta de acordo|autoriza)"
RE_JUSTIFICA_ID = r"(cpf|rg|documento)[^.]{0,80}(necessari|utilizad|usad|exigid|obrigatori|para emissao|nota fiscal|identificacao)|nota fiscal|exigencia legal|obrigacao legal|prevencao (a|de) fraude"
RE_MENORES = r"menor(es)? de (idade|18)|responsavel legal|maior(es)? de (18|idade)|18 anos|art 14|criancas e adolescentes"
RE_DPO = r"encarregad[oa]|\bdpo\b|data protection officer|encarregado pelo tratamento"
RE_DIREITOS = r"direitos do titular|seus direitos|art 18|acesso aos (seus )?dados|corrigir|portabilidade|eliminacao|exclusao (dos|de) (seus )?dados|anonimizacao"
RE_CANAL = r"\S+@\S+|formulario|canal|central de privacidade|portal do titular|fale com"
RE_REVOGACAO = r"revoga|retirar (o|seu) consentimento|descadastr|cancelar (a )?inscricao|unsubscribe|opt ?out|deixar de receber"
RE_CNPJ = r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"
RE_SENSIVEL_CONSENT = r"dados? sensive|saude|consentimento especifico|art 11|biometr|origem racial|religi"


class Regras:
    def __init__(self):
        self.lista = []

    def add(self, id_, categoria, titulo, status, detalhe, artigo, peso=1, recomendacao=""):
        self.lista.append({
            "id": id_, "categoria": categoria, "titulo": titulo, "status": status,
            "detalhe": detalhe, "artigo": artigo, "peso": peso, "recomendacao": recomendacao,
        })


# ---------------------------------------------------------------------------
# Finalidade e avaliação de campos
# ---------------------------------------------------------------------------
def detectar_finalidade(form: dict, extracao: dict, url: str) -> tuple[str, str]:
    tipos = [c["tipo_dado"] for c in form["campos"] if c["tipo_dado"] not in TIPOS_NEUTROS]
    texto_form = normalizar(form["texto"][:1500] + " " + (form.get("texto_botao") or "") + " " + form["id"])
    texto_pag = normalizar(" ".join([extracao["titulo"], extracao["h1"], urlparse(url).path]))

    if "senha" in tipos and len(tipos) <= 3 and "nome" not in tipos and not re.search(r"cadastr|criar conta|registr", texto_form):
        return "login", "campo de senha com poucos campos e sem nome"

    pontos = Counter()
    for chave, fin in FINALIDADES.items():
        for p in fin["palavras"]:
            p = normalizar(p)
            pontos[chave] += 3 * texto_form.count(p) + texto_pag.count(p)
    if set(tipos) <= {"email", "nome"} and "email" in tipos and pontos["newsletter"] >= pontos.most_common(1)[0][1] - 1:
        return "newsletter", "apenas e-mail (e nome) solicitados"
    if pontos and pontos.most_common(1)[0][1] > 0:
        chave, _ = pontos.most_common(1)[0]
        return chave, "palavras-chave no formulário/página"
    return "generico", "nenhuma palavra-chave de finalidade encontrada"


def avaliar_campo(campo: dict, finalidade: str) -> dict:
    fin = FINALIDADES[finalidade]
    t = campo["tipo_dado"]
    info = TIPOS_POR_ID.get(t, {"nome": "Não identificado", "categoria": "outro"})
    sensivel = bool(info.get("sensivel"))
    obrig = campo["obrigatorio"]

    if t in fin["necessarios"]:
        av, motivo = "necessario", f"Compatível com a finalidade “{fin['nome']}”."
    elif t in fin["justificaveis"]:
        av = "justificavel"
        motivo = f"Pode ser justificável para “{fin['nome']}”, desde que a finalidade seja informada"
        motivo += " – idealmente deveria ser opcional." if obrig else "."
    elif t in ("mensagem", "desconhecido", "foto") and t not in fin["necessarios"]:
        av, motivo = "indeterminado", "Não foi possível classificar automaticamente; requer análise contextual."
    else:
        av = "excessivo"
        motivo = f"Não é usualmente necessário para “{fin['nome']}” (princípio da necessidade, art. 6º, III)."

    if sensivel:
        motivo += " Dado pessoal SENSÍVEL: exige consentimento específico e destacado ou outra hipótese do art. 11."

    if av == "excessivo":
        sev = "alta" if (sensivel or (obrig and info["categoria"] in ("identificador", "financeiro"))) else ("media" if obrig else "baixa")
    elif av == "justificavel":
        sev = "media" if sensivel else ("baixa" if obrig else "nenhuma")
    else:
        sev = "nenhuma"

    return {**campo, "tipo_nome": info["nome"], "categoria_dado": info["categoria"], "sensivel": sensivel,
            "avaliacao": av, "severidade": sev, "motivo": motivo}


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------
def analisar(coleta: dict, extracao: dict, texto_politica: str | None = None,
             finalidade_forcada: str | None = None, politica_baixada: bool = False) -> dict:
    url = coleta["url_final"]
    https = url.startswith("https://")
    r = Regras()

    pagina = normalizar(extracao["texto_pagina"])
    politica = normalizar(texto_politica or "")
    pag_e_pol = pagina + " " + politica

    # ---------------- finalidades e campos ----------------
    formularios, campos, consentimentos = [], [], []
    for f in extracao["formularios"]:
        if finalidade_forcada and finalidade_forcada in FINALIDADES:
            fin, motivo_fin = finalidade_forcada, "definida pelo usuário"
        else:
            fin, motivo_fin = detectar_finalidade(f, extracao, url)
        formularios.append({"id": f["id"], "finalidade": fin, "finalidade_nome": FINALIDADES[fin]["nome"],
                            "motivo_finalidade": motivo_fin, "metodo": f["metodo"], "action": f["action"],
                            "action_terceiro": f["action_terceiro"], "qtd_campos": len(f["campos"])})
        for c in f["campos"]:
            if c["tipo_dado"] == "consentimento":
                txt = normalizar(c["rotulo"])
                consentimentos.append({
                    "form": f["id"], "texto": c["rotulo"], "marcado": c["marcado"], "obrigatorio": c["obrigatorio"],
                    "marketing": bool(re.search(RE_MARKETING, txt)), "termos": bool(re.search(RE_TERMOS, txt)),
                    "sensivel": bool(re.search(RE_SENSIVEL_CONSENT, txt)),
                })
            else:
                campos.append({"form": f["id"], **avaliar_campo(c, fin)})

    textos_forms = normalizar(" ".join(f["texto"] for f in extracao["formularios"]))
    tem_form = bool(campos)
    tipos_presentes = {c["tipo_dado"] for c in campos}
    exc = [c for c in campos if c["avaliacao"] == "excessivo"]
    just = [c for c in campos if c["avaliacao"] == "justificavel"]
    sens = [c for c in campos if c["sensivel"]]
    tipos_unicos = {(c["form"], c["tipo_dado"]) for c in campos}
    tipos_exc = {(c["form"], c["tipo_dado"]) for c in exc}

    # ======================= MINIMIZAÇÃO =======================
    cat = "minimizacao"
    if not tem_form:
        r.add("M1", cat, "Proporcionalidade dos dados solicitados", "na",
              "Nenhum campo de dado pessoal encontrado na página.", "Art. 6º, III", 3)
    else:
        razao = len(tipos_exc) / max(len(tipos_unicos), 1)
        nomes = ", ".join(sorted({c["tipo_nome"] for c in exc}))
        st = "falha" if (razao >= 0.3 or len(tipos_exc) >= 3) else ("parcial" if exc else "ok")
        det = (f"{len(tipos_exc)} de {len(tipos_unicos)} tipos de dado parecem excessivos para a finalidade"
               f" ({round(razao * 100)}%): {nomes}." if exc else
               f"Todos os {len(tipos_unicos)} tipos de dado solicitados são compatíveis com a finalidade.")
        r.add("M1", cat, "Proporcionalidade dos dados solicitados", st, det, "Art. 6º, III (necessidade)", 3,
              "Remova do formulário os dados que não são indispensáveis para a finalidade declarada.")

    if not sens:
        r.add("M2", cat, "Dados pessoais sensíveis", "ok" if tem_form else "na",
              "Nenhum dado sensível (saúde, religião, etnia, biometria etc.) solicitado.", "Art. 5º, II e art. 11", 3)
    else:
        consent_sens = any(c["sensivel"] for c in consentimentos)
        r.add("M2", cat, "Dados pessoais sensíveis", "parcial" if consent_sens else "falha",
              f"Solicita dado(s) sensível(is): {', '.join(sorted({c['tipo_nome'] for c in sens}))}. "
              + ("Há aceite específico para dados sensíveis." if consent_sens
                 else "Não foi identificado consentimento específico e destacado para esses dados."),
              "Art. 11", 3,
              "Só colete dados sensíveis se houver hipótese do art. 11; nesse caso, obtenha consentimento específico e destacado.")

    if tem_form:
        exc_obrig = [c for c in exc if c["obrigatorio"]]
        just_obrig = [c for c in just if c["obrigatorio"]]
        st = "falha" if exc_obrig else ("parcial" if just_obrig else "ok")
        det = (f"Campos possivelmente excessivos são OBRIGATÓRIOS: {', '.join(sorted({c['tipo_nome'] for c in exc_obrig}))}."
               if exc_obrig else
               f"Campos apenas justificáveis estão como obrigatórios: {', '.join(sorted({c['tipo_nome'] for c in just_obrig}))}."
               if just_obrig else "Nenhum campo não essencial é obrigatório.")
        r.add("M3", cat, "Obrigatoriedade de campos não essenciais", st, det, "Art. 6º, III e art. 9º, §3º", 2,
              "Torne opcionais os campos que não são indispensáveis e sinalize claramente quais são obrigatórios.")

    ids = [c for c in campos if c["tipo_dado"] in IDENTIFICADORES]
    if ids:
        ids_exc = [c for c in ids if c["avaliacao"] == "excessivo"]
        justificado = bool(re.search(RE_JUSTIFICA_ID, textos_forms))
        st = "falha" if ids_exc else ("ok" if justificado else "parcial")
        nomes = ", ".join(sorted({c["tipo_nome"] for c in ids}))
        det = (f"Solicita {', '.join(sorted({c['tipo_nome'] for c in ids_exc}))} sem necessidade aparente para a finalidade." if ids_exc else
               f"Solicita {nomes}; " + ("há justificativa junto ao formulário." if justificado
                                        else "não há explicação de por que o documento é necessário."))
        r.add("M4", cat, "Identificadores fortes (CPF, RG, CNH…)", st, det, "Art. 6º, I e III", 2,
              "Explique, junto ao campo, por que o documento é necessário (ex.: emissão de nota fiscal) ou remova-o.")
    elif tem_form:
        r.add("M4", cat, "Identificadores fortes (CPF, RG, CNH…)", "ok", "Nenhum documento de identificação solicitado.",
              "Art. 6º, III", 2)

    # ======================= TRANSPARÊNCIA =======================
    cat = "transparencia"
    link_pol = extracao["links"]["privacidade"]
    if link_pol:
        p = urlparse(link_pol)
        link_curto = (p.netloc + p.path).rstrip("/")  # sem parâmetros de rastreamento (utm, gclid...)
        texto_link = extracao.get("links_texto", {}).get("privacidade")
        det_t1 = f"Link “{texto_link}” encontrado ({link_curto})." if texto_link else f"Link encontrado ({link_curto})."
    r.add("T1", cat, "Política de privacidade acessível", "ok" if link_pol else "falha",
          det_t1 if link_pol else "Nenhum link para política de privacidade foi encontrado na página.",
          "Art. 9º", 3, "Publique uma política de privacidade e disponibilize o link em todas as páginas.")

    if tem_form:
        perto = any(re.search(r"privacidade|privacy|protecao de dados", normalizar(l["texto"] + " " + l["href"]))
                    for f in extracao["formularios"] for l in f["links"]) or "politica de privacidade" in textos_forms
        st = "ok" if perto else ("parcial" if link_pol else "falha")
        r.add("T2", cat, "Política referenciada junto ao formulário", st,
              "O formulário referencia a política de privacidade." if perto else
              ("A política existe, mas não é referenciada no formulário (apenas em outra parte da página)." if link_pol
               else "O formulário não referencia nenhuma política."),
              "Art. 9º, caput (informação clara e acessível)", 2,
              "Inclua o link da política de privacidade próximo ao botão de envio do formulário.")

        if re.search(PADRAO_FINALIDADE, textos_forms):
            st, det = "ok", "Há texto explicando a finalidade da coleta junto ao formulário."
        elif re.search(PADRAO_FINALIDADE, pagina):
            st, det = "parcial", "A finalidade é mencionada na página, mas não junto ao formulário."
        else:
            st, det = "falha", "Não foi encontrada explicação da finalidade específica da coleta."
        r.add("T3", cat, "Finalidade da coleta informada", st, det, "Art. 6º, I e art. 9º, I", 3,
              "Explique, ao lado do formulário, para que cada dado será usado (ex.: “usaremos seu telefone apenas para confirmar a entrega”).")

    if texto_politica:
        achados = [nome for k, (pad, nome) in TOPICOS_POLITICA.items() if re.search(pad, politica)]
        faltam = [nome for k, (pad, nome) in TOPICOS_POLITICA.items() if not re.search(pad, politica)]
        n, tot = len(achados), len(TOPICOS_POLITICA)
        st = "ok" if n >= 8 else ("parcial" if n >= 4 else "falha")
        r.add("T4", cat, "Conteúdo mínimo da política de privacidade", st,
              f"{n} de {tot} tópicos encontrados." + (f" Ausentes: {'; '.join(faltam)}." if faltam else ""),
              "Art. 9º, I a VII", 2, "Complete a política com os tópicos ausentes listados.")
    elif link_pol:
        r.add("T4", cat, "Conteúdo mínimo da política de privacidade", "na",
              "Não foi possível baixar a política para análise." if politica_baixada is False else "Política vazia.",
              "Art. 9º", 2)
    else:
        r.add("T4", cat, "Conteúdo mínimo da política de privacidade", "falha", "Sem política para analisar.", "Art. 9º", 2,
              "Publique uma política de privacidade contendo os elementos do art. 9º.")

    controlador = bool(re.search(RE_CNPJ, extracao["texto_pagina"] + " " + (texto_politica or ""))) or \
        bool(re.search(r"razao social|controlador", pag_e_pol))
    r.add("T5", cat, "Identificação do controlador", "ok" if controlador else "falha",
          "Razão social/CNPJ ou controlador identificado." if controlador else
          "Não foi possível identificar quem é o controlador dos dados (razão social/CNPJ).",
          "Art. 9º, III", 1, "Informe a razão social e o CNPJ do controlador na página ou na política.")

    envia_terceiros = bool(extracao["rastreadores"]) or any(f["action_terceiro"] for f in formularios)
    if envia_terceiros:
        menciona = bool(re.search(r"compartilha|terceiros|parceiros|operadores", politica))
        r.add("T6", cat, "Compartilhamento com terceiros informado", "ok" if menciona else ("parcial" if texto_politica else "falha"),
              ("Dados são enviados a terceiros (rastreadores ou formulário externo) e a política menciona compartilhamento."
               if menciona else "Há envio de dados a terceiros, mas não foi encontrada informação sobre compartilhamento."),
              "Art. 9º, V", 2, "Liste na política os terceiros/operadores que recebem dados e para qual finalidade.")
    else:
        r.add("T6", cat, "Compartilhamento com terceiros informado", "ok",
              "Não foi detectado envio direto de dados a terceiros.", "Art. 9º, V", 2)

    # ======================= CONSENTIMENTO =======================
    cat = "consentimento"
    if tem_form:
        ciencia = re.search(RE_CIENCIA, textos_forms)
        if consentimentos:
            st, det = "ok", f"{len(consentimentos)} caixa(s) de aceite encontrada(s)."
        elif ciencia:
            st, det = "parcial", "Há apenas aviso do tipo “ao clicar você concorda…”, sem manifestação ativa."
        else:
            st, det = "falha", ("Nenhum mecanismo de consentimento ou ciência identificado. (Se a base legal não for o "
                                "consentimento — ex.: execução de contrato — isso deve estar informado.)")
        r.add("C1", cat, "Mecanismo de consentimento/ciência", st, det, "Art. 7º, I e art. 8º", 2,
              "Inclua uma caixa de seleção (desmarcada) vinculada à política, ou informe a base legal utilizada.")

        if consentimentos:
            pre = [c for c in consentimentos if c["marcado"]]
            r.add("C2", cat, "Caixas de aceite pré-marcadas", "falha" if pre else "ok",
                  (f"{len(pre)} caixa(s) já vem(êm) marcada(s): “{pre[0]['texto'][:90]}”" if pre
                   else "Nenhuma caixa de aceite vem pré-marcada."),
                  "Art. 5º, XII e art. 8º (manifestação livre e inequívoca)", 3,
                  "Deixe todas as caixas de consentimento desmarcadas por padrão.")

        mkt = [c for c in consentimentos if c["marketing"]]
        if mkt:
            agrupado = [c for c in mkt if c["termos"]]
            mkt_obrig = [c for c in mkt if c["obrigatorio"]]
            st = "falha" if (agrupado or mkt_obrig) else "ok"
            det = ("Aceite de marketing está AGRUPADO com aceite dos termos/política." if agrupado else
                   "Aceite de comunicações de marketing é obrigatório para enviar o formulário." if mkt_obrig else
                   "Aceite de marketing é separado e opcional.")
            r.add("C3", cat, "Consentimento granular (marketing separado)", st, det, "Art. 8º, §4º (finalidades determinadas)", 2,
                  "Separe o aceite de marketing do aceite dos termos e torne-o opcional.")

        if "nascimento" in tipos_presentes:
            menc = re.search(RE_MENORES, pag_e_pol)
            r.add("C4", cat, "Tratamento de dados de crianças e adolescentes", "ok" if menc else "parcial",
                  ("Há menção ao tratamento de dados de menores/responsável legal." if menc else
                   "Coleta data de nascimento/idade, mas não informa como trata dados de menores de idade."),
                  "Art. 14", 1, "Informe a idade mínima ou exija consentimento do responsável legal para menores.")
    else:
        r.add("C1", cat, "Mecanismo de consentimento/ciência", "na", "Sem formulário na página.", "Art. 7º e 8º", 2)

    # ======================= COOKIES =======================
    cat = "cookies"
    agora = time.time()
    host = extracao["host"]
    cookies = []
    for c in coleta.get("cookies", []):
        dias = round((c["expira"] - agora) / 86400) if c.get("expira") and c["expira"] > 0 else None
        cookies.append({**c, "terceiro": eh_terceiro(c["dominio"], host), "dias": dias})
    terceiros = [c for c in cookies if c["terceiro"]]
    rastreadores = extracao["rastreadores"]
    banner = extracao["banner_cookies"]
    cmp = extracao["cmp"]
    nao_essenciais = bool(terceiros or rastreadores)

    if banner or cmp:
        r.add("K1", cat, "Aviso/banner de cookies", "ok",
              f"Banner detectado{f' (plataforma {cmp})' if cmp else ''}.", "Guia ANPD de Cookies; art. 9º", 2)
    elif nao_essenciais:
        r.add("K1", cat, "Aviso/banner de cookies", "falha",
              "Há cookies de terceiros/rastreadores, mas nenhum aviso de cookies foi detectado.", "Guia ANPD de Cookies; art. 9º", 2,
              "Implemente um banner de cookies com opções de aceitar, recusar e configurar.")
    else:
        r.add("K1", cat, "Aviso/banner de cookies", "na", "Não há cookies não essenciais detectados.", "Guia ANPD de Cookies", 2)

    if banner:
        st = "ok" if banner["recusar"] else ("parcial" if banner["configurar"] else "falha")
        det = ("Banner oferece botão para recusar cookies." if banner["recusar"] else
               "Não há botão “recusar”; apenas opção de configurar preferências." if banner["configurar"] else
               "Banner só permite aceitar (sem opção de recusa).")
        r.add("K2", cat, "Opção de recusar cookies", st, det, "Guia ANPD de Cookies; art. 8º, §5º", 3,
              "Ofereça um botão “Rejeitar” com o mesmo destaque do botão “Aceitar”.")
    elif cmp:
        r.add("K2", cat, "Opção de recusar cookies", "parcial",
              f"Plataforma {cmp} detectada, mas os botões não puderam ser verificados (banner carregado dinamicamente).",
              "Guia ANPD de Cookies", 3, "Verifique manualmente se há botão de recusa com o mesmo destaque.")
    elif nao_essenciais:
        r.add("K2", cat, "Opção de recusar cookies", "falha", "Não há mecanismo para recusar cookies não essenciais.",
              "Guia ANPD de Cookies; art. 8º, §5º", 3, "Implemente opção de recusa de cookies não essenciais.")
    else:
        r.add("K2", cat, "Opção de recusar cookies", "na", "Sem cookies não essenciais.", "Guia ANPD de Cookies", 3)

    pub = [t for t in rastreadores if t["nome"] in RASTREADORES_PUBLICIDADE]
    st = "ok" if not rastreadores else ("falha" if (pub or len(rastreadores) >= 3) else "parcial")
    r.add("K3", cat, "Rastreadores carregados antes do consentimento", st,
          (f"{len(rastreadores)} rastreador(es) carregado(s) sem interação do usuário: "
           f"{', '.join(t['nome'] for t in rastreadores)}." if rastreadores else
           "Nenhum rastreador de terceiros carregado no primeiro acesso."),
          "Guia ANPD de Cookies; art. 7º, I", 3,
          "Bloqueie scripts de analytics/publicidade até o usuário consentir (consent mode / bloqueio prévio).")

    if cookies:
        st = "ok" if not terceiros else ("parcial" if len(terceiros) <= 3 else "falha")
        r.add("K4", cat, "Cookies de terceiros", st,
              f"{len(cookies)} cookie(s) no primeiro acesso, {len(terceiros)} de terceiros"
              + (f" ({', '.join(sorted({c['dominio'] for c in terceiros})[:5])})." if terceiros else "."),
              "Guia ANPD de Cookies", 2, "Reduza cookies de terceiros e só os ative após consentimento.")
        longos = [c for c in cookies if c["dias"] and c["dias"] > 395]
        r.add("K5", cat, "Duração dos cookies", "parcial" if longos else "ok",
              (f"{len(longos)} cookie(s) com validade acima de 13 meses (máx. {max(c['dias'] for c in longos)} dias)."
               if longos else "Nenhum cookie com validade excessiva (> 13 meses)."),
              "Art. 6º, III e art. 15 (término do tratamento)", 1, "Reduza a validade dos cookies ao mínimo necessário.")
    else:
        r.add("K4", cat, "Cookies de terceiros", "ok", "Nenhum cookie definido no primeiro acesso.", "Guia ANPD de Cookies", 2)

    if cookies or rastreadores:
        tem_pol_cookies = bool(extracao["links"]["cookies"]) or "cookie" in politica
        r.add("K6", cat, "Política de cookies", "ok" if tem_pol_cookies else "falha",
              "Há política/aviso de cookies acessível." if tem_pol_cookies else
              "Não foi encontrada política explicando os cookies utilizados.",
              "Art. 9º; Guia ANPD de Cookies", 1, "Publique uma política de cookies com finalidade e duração de cada cookie.")

    # ======================= SEGURANÇA =======================
    cat = "seguranca"
    r.add("S1", cat, "Conexão segura (HTTPS)", "ok" if https else "falha",
          "A página usa HTTPS." if https else "A página NÃO usa HTTPS: dados trafegam sem criptografia.",
          "Art. 46", 3, "Habilite HTTPS (TLS) em todo o site.")

    if tem_form:
        inseguros = [f for f in formularios if f["action"].startswith("http://")]
        via_get = [f for f in formularios if f["metodo"] == "get" and any(c["form"] == f["id"] and c["tipo_dado"] not in ("mensagem", "desconhecido") for c in campos)]
        st = "falha" if (inseguros or via_get) else "ok"
        problemas = (["envia dados para endereço sem HTTPS"] if inseguros else []) + \
            (["usa método GET, expondo dados pessoais na URL, histórico e logs"] if via_get else [])
        det = ("Formulário " + " e ".join(problemas) + ".") if problemas else \
            "Formulários enviam dados por canal seguro (POST/HTTPS)."
        r.add("S2", cat, "Envio seguro do formulário", st, det, "Art. 46", 3,
              "Envie formulários via POST para endpoints HTTPS.")

    h = coleta.get("headers", {})
    csp = h.get("content-security-policy", "")
    cab = {
        "Strict-Transport-Security": bool(h.get("strict-transport-security")),
        "Content-Security-Policy": bool(csp),
        "X-Content-Type-Options": bool(h.get("x-content-type-options")),
        "X-Frame-Options / frame-ancestors": bool(h.get("x-frame-options")) or "frame-ancestors" in csp,
        "Referrer-Policy": bool(h.get("referrer-policy")),
    }
    n = sum(cab.values())
    r.add("S3", cat, "Cabeçalhos de segurança HTTP", "ok" if n >= 4 else ("parcial" if n >= 2 else "falha"),
          f"{n} de 5 presentes. Ausentes: {', '.join(k for k, v in cab.items() if not v) or 'nenhum'}.",
          "Art. 46 (medidas técnicas de segurança)", 2, "Configure os cabeçalhos de segurança ausentes no servidor.")

    if https:
        misto = extracao["conteudo_misto"]
        r.add("S4", cat, "Conteúdo misto (HTTP em página HTTPS)", "falha" if misto else "ok",
              f"{len(misto)} recurso(s) carregado(s) via HTTP." if misto else "Nenhum recurso inseguro carregado.",
              "Art. 46", 1, "Carregue todos os recursos via HTTPS.")

    proprios = [c for c in cookies if not c["terceiro"]]
    if https and proprios:
        sem_flag = [c for c in proprios if not c["secure"]]
        r.add("S5", cat, "Atributos de segurança dos cookies", "parcial" if sem_flag else "ok",
              (f"{len(sem_flag)} cookie(s) próprio(s) sem o atributo Secure." if sem_flag
               else "Cookies próprios usam o atributo Secure."),
              "Art. 46", 1, "Defina Secure, HttpOnly e SameSite nos cookies.")

    # ======================= DIREITOS / GOVERNANÇA =======================
    cat = "direitos"
    dpo = re.search(RE_DPO, pag_e_pol)
    r.add("D1", cat, "Encarregado (DPO) identificado", "ok" if dpo else "falha",
          "Há menção ao encarregado/DPO e forma de contato." if dpo else
          "Não foi encontrada identificação do encarregado pelo tratamento de dados.",
          "Art. 41, §1º", 3, "Divulgue nome e contato do encarregado (DPO) de forma clara.")

    direitos = re.search(RE_DIREITOS, pag_e_pol)
    canal = re.search(RE_CANAL, politica or pagina)
    st = "ok" if (direitos and canal) else ("parcial" if direitos else "falha")
    r.add("D2", cat, "Canal para exercício de direitos", st,
          ("Direitos do titular informados com canal de atendimento." if st == "ok" else
           "Direitos são citados, mas sem canal claro para exercê-los." if st == "parcial" else
           "Não há informação sobre os direitos do titular (acesso, correção, exclusão…)."),
          "Art. 18", 2, "Informe os direitos do art. 18 e um canal (e-mail/formulário) para exercê-los.")

    rev = re.search(RE_REVOGACAO, pag_e_pol)
    r.add("D3", cat, "Revogação do consentimento", "ok" if rev else "parcial",
          "Há informação de como revogar o consentimento/descadastrar." if rev else
          "Não foi encontrada informação sobre como revogar o consentimento.",
          "Art. 8º, §5º e art. 18, IX", 1, "Explique como o titular pode revogar o consentimento a qualquer momento.")

    # ======================= PONTUAÇÃO =======================
    cats = {}
    for k, meta in CATEGORIAS.items():
        aplic = [x for x in r.lista if x["categoria"] == k and x["status"] in PONTOS]
        if aplic:
            nota = sum(PONTOS[x["status"]] * x["peso"] for x in aplic) / sum(x["peso"] for x in aplic)
            cats[k] = {**meta, "nota": round(nota * 100), "regras": len(aplic)}
        else:
            cats[k] = {**meta, "nota": None, "regras": 0}
    validas = [c for c in cats.values() if c["nota"] is not None]
    score = round(sum(c["nota"] * c["peso"] for c in validas) / sum(c["peso"] for c in validas)) if validas else 0
    if score >= 80:
        classe, nivel = "Adequado", "ok"
    elif score >= 50:
        classe, nivel = "Adequação parcial", "parcial"
    else:
        classe, nivel = "Baixa adequação", "falha"

    # ======================= RISCOS =======================
    riscos = []
    for x in r.lista:
        if x["status"] == "falha":
            nv = "alto" if x["peso"] >= 3 else "medio"
        elif x["status"] == "parcial":
            nv = "medio" if x["peso"] >= 3 else "baixo"
        else:
            continue
        riscos.append({"nivel": nv, "titulo": x["titulo"], "descricao": x["detalhe"], "artigo": x["artigo"],
                       "recomendacao": x["recomendacao"], "origem": "regras"})
    ordem = {"alto": 0, "medio": 1, "baixo": 2}
    riscos.sort(key=lambda z: ordem[z["nivel"]])

    # ======================= VERIFICAÇÕES OBJETIVAS =======================
    status = {x["id"]: x["status"] for x in r.lista}
    objetivas = [
        ("CPF solicitado", "cpf" in tipos_presentes),
        ("E-mail solicitado", "email" in tipos_presentes),
        ("Telefone solicitado", "telefone" in tipos_presentes),
        ("Dados sensíveis solicitados", bool(sens)),
        ("Política de privacidade", bool(link_pol)),
        ("Finalidade da coleta explícita", status.get("T3") == "ok"),
        ("Caixa de consentimento", bool(consentimentos)),
        ("Banner de cookies", bool(banner or cmp)),
        ("Botão “recusar” cookies", bool(banner and banner["recusar"])),
        ("Encarregado (DPO) informado", bool(dpo)),
        ("HTTPS", https),
    ]

    return {
        "score": score,
        "classificacao": classe,
        "nivel": nivel,
        "categorias": cats,
        "regras": r.lista,
        "riscos": riscos,
        "verificacoes_objetivas": [{"item": a, "valor": b} for a, b in objetivas],
        "formularios": formularios,
        "campos": campos,
        "consentimentos": consentimentos,
        "cookies": cookies,
        "rastreadores": rastreadores,
        "resumo_campos": {
            "total": len(campos),
            "necessarios": sum(c["avaliacao"] == "necessario" for c in campos),
            "justificaveis": len(just),
            "excessivos": len(exc),
            "indeterminados": sum(c["avaliacao"] == "indeterminado" for c in campos),
            "sensiveis": len(sens),
            "obrigatorios": sum(c["obrigatorio"] for c in campos),
        },
    }
