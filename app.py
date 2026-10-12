"""
LGPD Web Analyzer - servidor web (Flask).

Execução:
    py app.py
e acesse http://127.0.0.1:5000
"""

import os

try:  # carrega variáveis do arquivo .env, se o python-dotenv estiver instalado
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, jsonify, render_template, request, send_from_directory

from lgpd import agente_ia
from lgpd.analisador import analisar_url, carregar, listar_historico
from lgpd.catalogo import FINALIDADES
from lgpd.regras import CATEGORIAS

app = Flask(__name__)
app.json.ensure_ascii = False
app.json.sort_keys = False  # mantém a ordem das categorias definida no motor de regras


@app.get("/")
def index():
    finalidades = [(k, v["nome"]) for k, v in FINALIDADES.items()]
    return render_template("index.html", finalidades=finalidades, categorias=CATEGORIAS,
                           ia_disponivel=agente_ia.disponivel(), ia_provedor=agente_ia.nome_provedor())


@app.post("/api/analisar")
def api_analisar():
    dados = request.get_json(silent=True) or {}
    try:
        relatorio = analisar_url(
            dados.get("url", ""),
            finalidade=dados.get("finalidade") or None,
            usar_ia=bool(dados.get("usar_ia", True)),
        )
        return jsonify(relatorio)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:  # erro de rede, timeout, página inacessível...
        return jsonify({"erro": f"Não foi possível analisar a página: {str(e).splitlines()[0][:300]}"}), 502


@app.get("/api/historico")
def api_historico():
    return jsonify(listar_historico())


@app.get("/api/historico/<id_>")
def api_historico_item(id_):
    rel = carregar(id_)
    return (jsonify(rel), 200) if rel else (jsonify({"erro": "Análise não encontrada."}), 404)


@app.get("/exemplos/<path:nome>")
def exemplos(nome):
    """Páginas de demonstração para testar o analisador (uma ruim e uma adequada)."""
    return send_from_directory("exemplos", nome)


if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=porta, debug=True, threaded=True)
