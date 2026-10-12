"""
Catálogo de conhecimento usado pelo motor de regras.

Aqui ficam, de forma declarativa, os tipos de dados pessoais reconhecidos,
as finalidades (contextos) de formulário e quais dados cada finalidade
normalmente justifica, além das listas de rastreadores e CMPs conhecidos.
Manter isso separado do motor facilita explicar e evoluir as regras no TCC.
"""

import re
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[_\-\[\]\.]+", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


# ---------------------------------------------------------------------------
# Tipos de dados pessoais
# ---------------------------------------------------------------------------
# A ORDEM IMPORTA: padrões mais específicos vêm antes dos genéricos
# (ex.: "nome da mãe" antes de "nome"; "data de nascimento" antes de "data").
#
# categoria: comum | identificador | sensivel | financeiro | credencial | outro
# sensivel=True  -> dado pessoal sensível (LGPD art. 5º, II e art. 11)
TIPOS_DADOS = [
    # --- consentimento / controle (não são dados pessoais em si) ---
    {"id": "consentimento", "nome": "Aceite / consentimento", "categoria": "controle",
     "padrao": r"aceito|concordo|autorizo|consinto|li e|declaro|termos|politica de privacidade|receber (e mail|ofertas|novidades|comunica)|newsletter|optin|opt in"},

    # --- sensíveis (art. 5º, II) ---
    {"id": "raca", "nome": "Origem racial ou étnica", "categoria": "sensivel", "sensivel": True,
     "padrao": r"\braca\b|etnia|etnic|cor da pele|\bcor\b.*(raca|pele)|ethnic|race"},
    {"id": "religiao", "nome": "Convicção religiosa", "categoria": "sensivel", "sensivel": True,
     "padrao": r"religi|crenca|igreja|religion"},
    {"id": "politica", "nome": "Opinião política / filiação", "categoria": "sensivel", "sensivel": True,
     "padrao": r"partido|politic(a|o) (partid|preferid)|opiniao politica|filiacao|sindica"},
    {"id": "orientacao_sexual", "nome": "Vida sexual / orientação sexual", "categoria": "sensivel", "sensivel": True,
     "padrao": r"orientacao sexual|sexualidade|vida sexual|sexual orientation"},
    {"id": "saude", "nome": "Dado de saúde", "categoria": "sensivel", "sensivel": True,
     "padrao": r"saude|doenca|deficien|\bpcd\b|medicament|alergi|tipo sangu|sanguineo|\bcid\b|diagnost|gestante|gravid|health|plano de saude|convenio"},
    {"id": "genetico", "nome": "Dado genético", "categoria": "sensivel", "sensivel": True,
     "padrao": r"genetic|\bdna\b"},
    {"id": "biometria", "nome": "Biometria / imagem facial", "categoria": "sensivel", "sensivel": True,
     "padrao": r"biometr|selfie|reconhecimento facial|impressao digital|foto do rosto|facial"},

    # --- identificadores fortes ---
    {"id": "cpf", "nome": "CPF", "categoria": "identificador",
     "padrao": r"\bcpf\b|cadastro de pessoa fisica|cpf ?cnpj"},
    {"id": "cnpj", "nome": "CNPJ", "categoria": "identificador", "padrao": r"\bcnpj\b"},
    {"id": "rg", "nome": "RG / documento de identidade", "categoria": "identificador",
     "padrao": r"\brg\b|identidade(?! de genero)|registro geral|orgao emissor"},
    {"id": "cnh", "nome": "CNH", "categoria": "identificador", "padrao": r"\bcnh\b|habilitacao"},
    {"id": "passaporte", "nome": "Passaporte", "categoria": "identificador", "padrao": r"passaporte|passport"},
    {"id": "titulo_eleitor", "nome": "Título de eleitor", "categoria": "identificador", "padrao": r"titulo de eleitor|eleitor"},
    {"id": "pis", "nome": "PIS / NIS / CTPS", "categoria": "identificador", "padrao": r"\bpis\b|\bnis\b|\bpasep\b|\bctps\b|carteira de trabalho"},

    # --- financeiros ---
    {"id": "cartao", "nome": "Dados de cartão", "categoria": "financeiro",
     "padrao": r"cartao|card ?number|\bcvv\b|\bcvc\b|cc ?(number|exp|csc)|validade do cartao|titular do cartao"},
    {"id": "conta_bancaria", "nome": "Dados bancários", "categoria": "financeiro",
     "padrao": r"agencia|conta (corrente|bancaria|poupanca)|\bbanco\b|chave pix|\bpix\b"},
    {"id": "renda", "nome": "Renda / salário", "categoria": "financeiro",
     "padrao": r"renda|salari|income|faturamento|patrimonio"},

    # --- credenciais ---
    {"id": "senha", "nome": "Senha", "categoria": "credencial", "padrao": r"senha|password|passwd|\bpwd\b"},
    {"id": "usuario", "nome": "Nome de usuário", "categoria": "credencial", "padrao": r"usuario|username|user name|\blogin\b|apelido|nickname"},

    # --- dados comuns ---
    {"id": "nome_mae", "nome": "Nome da mãe / filiação", "categoria": "comum",
     "padrao": r"nome da mae|\bmae\b|mother|filiacao|nome do pai"},
    {"id": "nascimento", "nome": "Data de nascimento / idade", "categoria": "comum",
     "padrao": r"nasc|birth|\bbday\b|\bdob\b|\bidade\b|\bage\b"},
    {"id": "email", "nome": "E-mail", "categoria": "comum", "padrao": r"e ?mail|correio eletronico"},
    {"id": "telefone", "nome": "Telefone / celular", "categoria": "comum",
     "padrao": r"\btel\b|telefone|\bfone\b|celular|whats|phone|mobile|\bddd\b"},
    {"id": "estado_civil", "nome": "Estado civil", "categoria": "comum", "padrao": r"estado civil|marital|casado|conjuge"},
    {"id": "cep", "nome": "CEP", "categoria": "comum", "padrao": r"\bcep\b|\bzip\b|postal"},
    {"id": "endereco", "nome": "Endereço", "categoria": "comum",
     "padrao": r"endereco|address|\brua\b|logradouro|bairro|cidade|city|municipio|\bestado\b|\buf\b|numero|complemento|street"},
    {"id": "genero", "nome": "Gênero / sexo", "categoria": "comum", "padrao": r"genero|\bsexo\b|gender"},
    {"id": "nacionalidade", "nome": "Nacionalidade / naturalidade", "categoria": "comum",
     "padrao": r"nacionalidade|naturalidade|nationality"},
    {"id": "escolaridade", "nome": "Escolaridade", "categoria": "comum", "padrao": r"escolaridade|formacao|grau de instrucao"},
    {"id": "profissao", "nome": "Profissão / empresa", "categoria": "comum",
     "padrao": r"profiss|ocupacao|cargo|empresa|company|job|trabalho"},
    {"id": "redes_sociais", "nome": "Redes sociais", "categoria": "comum",
     "padrao": r"instagram|facebook|linkedin|twitter|tiktok|rede social"},
    {"id": "localizacao", "nome": "Geolocalização", "categoria": "comum", "padrao": r"latitude|longitude|geoloc|localizacao"},
    {"id": "foto", "nome": "Foto / arquivo pessoal", "categoria": "comum", "padrao": r"\bfoto\b|photo|avatar|curriculo|\bcv\b|anexo|upload"},
    {"id": "nome", "nome": "Nome", "categoria": "comum",
     "padrao": r"\bnome\b|\bname\b|fullname|full name|first name|last name|sobrenome|surname|fname|lname"},

    # --- conteúdo livre ---
    {"id": "mensagem", "nome": "Mensagem / texto livre", "categoria": "outro",
     "padrao": r"mensagem|message|assunto|subject|comentario|duvida|observac|descricao|comment"},
]

TIPOS_POR_ID = {t["id"]: t for t in TIPOS_DADOS}

# Mapeamento direto do atributo HTML autocomplete -> tipo de dado
AUTOCOMPLETE = {
    "name": "nome", "given-name": "nome", "family-name": "nome", "additional-name": "nome",
    "email": "email", "tel": "telefone", "tel-national": "telefone", "tel-local": "telefone",
    "bday": "nascimento", "bday-day": "nascimento", "bday-month": "nascimento", "bday-year": "nascimento",
    "sex": "genero", "postal-code": "cep", "street-address": "endereco", "address-line1": "endereco",
    "address-line2": "endereco", "address-level1": "endereco", "address-level2": "endereco",
    "country": "endereco", "country-name": "endereco",
    "cc-number": "cartao", "cc-csc": "cartao", "cc-exp": "cartao", "cc-name": "cartao",
    "username": "usuario", "current-password": "senha", "new-password": "senha",
    "organization": "profissao", "organization-title": "profissao", "photo": "foto",
}

# Atributo type do input -> tipo de dado
TIPO_INPUT = {"email": "email", "tel": "telefone", "password": "senha", "file": "foto"}


# ---------------------------------------------------------------------------
# Finalidades de formulário e dados que cada uma justifica
# ---------------------------------------------------------------------------
# necessarios  -> essenciais para a finalidade
# justificaveis -> aceitáveis se houver justificativa (idealmente opcionais)
# Qualquer outro dado é considerado potencialmente EXCESSIVO (art. 6º, III).
FINALIDADES = {
    "login": {
        "nome": "Login / autenticação",
        "palavras": ["login", "entrar", "acessar conta", "acesse sua conta", "sign in", "esqueci minha senha"],
        "necessarios": {"email", "usuario", "senha", "cpf"},
        "justificaveis": set(),
    },
    "newsletter": {
        "nome": "Newsletter / lista de e-mails",
        "palavras": ["newsletter", "inscreva", "assine", "receba novidades", "receber novidades", "subscribe", "lista de e-mail"],
        "necessarios": {"email"},
        "justificaveis": {"nome"},
    },
    "contato": {
        "nome": "Contato / atendimento",
        "palavras": ["contato", "fale conosco", "entre em contato", "atendimento", "sac", "ouvidoria", "duvida", "contact"],
        "necessarios": {"nome", "email", "mensagem"},
        "justificaveis": {"telefone", "cpf"},
    },
    "cadastro": {
        "nome": "Cadastro / criação de conta",
        "palavras": ["cadastro", "cadastre", "criar conta", "crie sua conta", "registre", "registro", "sign up", "inscricao"],
        "necessarios": {"nome", "email", "senha"},
        "justificaveis": {"telefone", "usuario", "nascimento", "cpf", "cep"},
    },
    "compra": {
        "nome": "Compra / checkout / entrega",
        "palavras": ["checkout", "finalizar compra", "pagamento", "entrega", "frete", "carrinho", "pedido", "comprar"],
        "necessarios": {"nome", "email", "cpf", "cnpj", "endereco", "cep", "telefone", "cartao"},
        "justificaveis": {"nascimento", "senha", "usuario"},
    },
    "emprego": {
        "nome": "Candidatura a vaga / currículo",
        "palavras": ["vaga", "curriculo", "candidat", "trabalhe conosco", "carreira", "processo seletivo", "recrutamento"],
        "necessarios": {"nome", "email", "telefone", "foto", "profissao", "escolaridade"},
        "justificaveis": {"endereco", "cep", "nascimento", "cpf", "redes_sociais", "mensagem", "estado_civil", "pis"},
    },
    "financeiro": {
        "nome": "Serviço financeiro / crédito / abertura de conta",
        "palavras": ["abertura de conta", "abra sua conta", "credito", "emprestimo", "financiamento", "cartao de credito", "simulacao", "investimento"],
        "necessarios": {"nome", "cpf", "rg", "email", "telefone", "endereco", "cep", "nascimento", "renda", "nome_mae"},
        "justificaveis": {"profissao", "estado_civil", "conta_bancaria", "nacionalidade", "senha", "biometria", "cnh"},
    },
    "saude": {
        "nome": "Agendamento / serviço de saúde",
        "palavras": ["agendamento", "agende", "consulta", "exame", "paciente", "clinica", "hospital", "convenio", "medico"],
        "necessarios": {"nome", "cpf", "nascimento", "telefone", "email"},
        "justificaveis": {"saude", "endereco", "cep", "genero", "rg", "mensagem"},
    },
    "evento": {
        "nome": "Inscrição em evento / curso",
        "palavras": ["evento", "webinar", "palestra", "curso", "ingresso", "inscreva-se no", "workshop"],
        "necessarios": {"nome", "email"},
        "justificaveis": {"telefone", "profissao", "cpf", "endereco"},
    },
    "generico": {
        "nome": "Formulário genérico",
        "palavras": [],
        "necessarios": {"nome", "email"},
        "justificaveis": {"telefone", "mensagem"},
    },
}

# Tipos que nunca contam como excesso (controle ou neutros)
TIPOS_NEUTROS = {"consentimento"}


# ---------------------------------------------------------------------------
# Rastreadores e plataformas de consentimento (CMP)
# ---------------------------------------------------------------------------
RASTREADORES = {
    "google-analytics.com": "Google Analytics",
    "analytics.google.com": "Google Analytics",
    "googletagmanager.com": "Google Tag Manager",
    "doubleclick.net": "Google Ads / DoubleClick",
    "googleadservices.com": "Google Ads",
    "googlesyndication.com": "Google AdSense",
    "connect.facebook.net": "Meta Pixel",
    "facebook.com/tr": "Meta Pixel",
    "hotjar.com": "Hotjar",
    "clarity.ms": "Microsoft Clarity",
    "bat.bing.com": "Microsoft Ads",
    "analytics.tiktok.com": "TikTok Pixel",
    "snap.licdn.com": "LinkedIn Insight",
    "px.ads.linkedin.com": "LinkedIn Ads",
    "static.ads-twitter.com": "X/Twitter Ads",
    "taboola.com": "Taboola",
    "outbrain.com": "Outbrain",
    "criteo.com": "Criteo",
    "criteo.net": "Criteo",
    "rdstation.com": "RD Station",
    "d335luupugsy2.cloudfront.net": "RD Station",
    "hs-scripts.com": "HubSpot",
    "hs-analytics.net": "HubSpot",
    "mixpanel.com": "Mixpanel",
    "segment.com": "Segment",
    "amplitude.com": "Amplitude",
    "yandex.ru/metrika": "Yandex Metrica",
    "mc.yandex.ru": "Yandex Metrica",
    "pinimg.com/ct": "Pinterest Tag",
    "quantserve.com": "Quantcast",
    "scorecardresearch.com": "Comscore",
}

CMPS = {
    "onetrust": "OneTrust", "cookielaw.org": "OneTrust", "cookiebot": "Cookiebot",
    "didomi": "Didomi", "quantcast": "Quantcast Choice", "cookieyes": "CookieYes",
    "goadopt.io": "AdOpt", "adopt": "AdOpt", "termly": "Termly", "usercentrics": "Usercentrics",
    "iubenda": "iubenda", "trustarc": "TrustArc", "complianz": "Complianz", "lgpd-cookie": "LGPD Cookie",
}

# Tópicos esperados numa política de privacidade (LGPD art. 9º e correlatos)
TOPICOS_POLITICA = {
    "finalidade": (r"finalidade|para que (usamos|utilizamos)|como (usamos|utilizamos)", "Finalidade do tratamento (art. 9º, I)"),
    "retencao": (r"retencao|armazenad[oa]s? (por|durante)|prazo|periodo de armazenamento|por quanto tempo", "Forma e duração do tratamento (art. 9º, II)"),
    "controlador": (r"controlador|razao social|\bcnpj\b", "Identificação do controlador (art. 9º, III)"),
    "contato": (r"encarregado|\bdpo\b|data protection officer|contato.*privacidade|privacidade@|dpo@|lgpd@", "Contato / encarregado (art. 9º, IV e art. 41)"),
    "compartilhamento": (r"compartilha|terceiros|parceiros|operadores", "Uso compartilhado de dados (art. 9º, V)"),
    "direitos": (r"direitos do titular|seus direitos|art\.? ?18|acesso aos dados|correcao|portabilidade|eliminacao|exclusao dos dados", "Direitos do titular (art. 9º, VII e art. 18)"),
    "base_legal": (r"base legal|bases legais|legitimo interesse|execucao de contrato|obrigacao legal|consentimento", "Bases legais (art. 7º)"),
    "seguranca": (r"seguranca|criptograf|medidas tecnicas", "Medidas de segurança (art. 46)"),
    "transferencia": (r"transferencia internacional|outros paises|exterior|fora do brasil", "Transferência internacional (art. 33)"),
    "cookies": (r"cookie", "Uso de cookies"),
    "atualizacao": (r"atualizad[ao] em|ultima atualizacao|vigente|versao", "Data de atualização"),
}

# Textos que indicam finalidade explicada junto ao formulário
PADRAO_FINALIDADE = (
    r"finalidade|utilizaremos (seus|os) dados|usaremos (seus|os) dados|seus dados (serao|sao) (usados|utilizados|tratados)|"
    r"para (fins|que possamos)|com o objetivo de|os dados coletados|tratamento (dos|de) (seus )?dados|"
    r"utilizad[oa]s? (apenas|somente|exclusivamente) para|necessario para|precisamos (do|de|dos)|why we ask|"
    r"(cpf|telefone|e mail|dados) (e|sera|serao) (usado|utilizado|necessario)"
)
