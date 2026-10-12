// LGPD Web Analyzer - front-end do portal
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

// Todo conteúdo vindo da página analisada é de terceiros: sempre escapar.
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ROTULO_ST = { ok: "Atende", parcial: "Parcial", falha: "Não atende", na: "Não se aplica" };
const ICONE_ST = { ok: "✓", parcial: "◐", falha: "✕", na: "–" };
const st = (s, texto) => `<span class="st st-${s}"><i></i>${ICONE_ST[s]} ${esc(texto ?? ROTULO_ST[s])}</span>`;

const AVAL = {
  necessario: ["ok", "Necessário"],
  justificavel: ["parcial", "Justificável"],
  excessivo: ["falha", "Excessivo"],
  indeterminado: ["na", "Indeterminado"],
};
const aval = (a) => (a && AVAL[a] ? st(AVAL[a][0], AVAL[a][1]) : `<span class="st st-na">—</span>`);
const NIVEL_RISCO = { alto: "Risco alto", medio: "Risco médio", baixo: "Risco baixo" };

// mostra só domínio + caminho (sem utm, gclid etc.)
const urlCurta = (u) => {
  try { const p = new URL(u); return (p.host + p.pathname).replace(/\/$/, ""); } catch { return u; }
};

let relatorioAtual = null;
let timerEtapas = null;

// ------------------------------------------------------------------ navegação lateral
$$("[data-nav]").forEach((a) =>
  a.addEventListener("click", () => {
    $$("[data-nav]").forEach((x) => x.classList.remove("ativo"));
    a.classList.add("ativo");
  })
);

// ------------------------------------------------------------------ análise
$("#form-analise").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = $("#url").value.trim();
  if (!url) return;
  iniciarCarregamento();
  try {
    const resp = await fetch("/api/analisar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, finalidade: $("#finalidade").value, usar_ia: $("#usar-ia").checked }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "Erro inesperado.");
    mostrar(dados);
    carregarHistorico();
  } catch (err) {
    $("#erro").innerHTML = `<b>Não foi possível concluir a análise.</b><br>${esc(err.message)}`;
    $("#erro").hidden = false;
  } finally {
    pararCarregamento();
  }
});

$$("[data-exemplo]").forEach((a) =>
  a.addEventListener("click", (e) => {
    e.preventDefault();
    $("#url").value = location.origin + a.dataset.exemplo;
    $("#url").focus();
  })
);

function iniciarCarregamento() {
  $("#btn").disabled = true;
  $("#erro").hidden = true;
  $("#resultado").hidden = true;
  $("#carregando").hidden = false;
  const itens = $$("#etapas li");
  const usarIA = $("#usar-ia").checked;
  itens[3].style.display = usarIA ? "" : "none";
  let i = 0;
  const marcar = () => itens.forEach((li, j) => { li.className = j < i ? "feita" : j === i ? "ativa" : ""; });
  marcar();
  // Indicação visual de progresso: o servidor processa tudo em uma única requisição.
  const tempos = [6000, 2500, 1500, 9000];
  const avancar = () => {
    if (i >= itens.length - 1) return;
    i++;
    if (!usarIA && i === 3) i++;
    marcar();
    timerEtapas = setTimeout(avancar, tempos[i] || 4000);
  };
  timerEtapas = setTimeout(avancar, tempos[0]);
}

function pararCarregamento() {
  clearTimeout(timerEtapas);
  $("#btn").disabled = false;
  $("#carregando").hidden = true;
}

// ------------------------------------------------------------------ dashboard
function mostrar(d) {
  relatorioAtual = d;
  const naoAtende = d.regras.filter((r) => r.status === "falha").length;
  const iaOk = d.ia && d.ia.disponivel;

  $("#resultado").innerHTML = `
  <div class="painel">
    <div class="painel-corpo cab-resultado">
      <div>
        <span class="rotulo">Página analisada</span>
        <div class="url-analisada"><a href="${esc(d.url)}" target="_blank" rel="noopener noreferrer">${esc(urlCurta(d.url))}</a></div>
        <div class="meta quebra">${esc(d.titulo)} · ${new Date(d.data).toLocaleString("pt-BR")} · coleta via ${esc(d.coleta.metodo)}
          ${d.coleta.aviso ? `<br>⚠ ${esc(d.coleta.aviso)}` : ""}</div>
      </div>
      <div class="acoes">
        <button class="btn-sec" onclick="imprimir()">Exportar PDF</button>
        <button class="btn-sec" onclick="baixarJSON()">Baixar JSON</button>
      </div>
    </div>
    <div class="abas" role="tablist">
      <button class="ativa" data-aba="visao">Visão geral</button>
      <button data-aba="campos">Campos <span class="contador">${d.campos.length}</span></button>
      <button data-aba="checklist">Checklist LGPD <span class="contador">${naoAtende} não atende</span></button>
      <button data-aba="ia">Parecer da IA</button>
      <button data-aba="cookies">Cookies e rastreadores <span class="contador">${d.cookies.length + d.rastreadores.length}</span></button>
    </div>
  </div>

  <div class="aba-painel ativa" id="aba-visao">${visaoGeral(d)}</div>

  <div class="aba-painel" id="aba-campos">
    <div class="painel">
      <div class="painel-cab"><h2>Avaliação de necessidade dos campos</h2><span class="sub">Princípio da necessidade — art. 6º, III</span></div>
      <div class="info-finalidade quebra">Finalidade considerada: ${d.formularios.map((f) =>
        `<b>${esc(f.finalidade_nome)}</b> <small>(formulário “${esc(f.id)}” — ${esc(f.motivo_finalidade)})</small>`).join("; ") || "nenhum formulário encontrado"}</div>
      ${tabelaCampos(d)}
      ${tabelaConsentimentos(d)}
    </div>
  </div>

  <div class="aba-painel" id="aba-checklist">
    <div class="painel">
      <div class="painel-cab"><h2>Checklist LGPD — motor de regras</h2><span class="sub">${d.regras.length} regras avaliadas</span></div>
      ${regrasPorCategoria(d)}
    </div>
  </div>

  <div class="aba-painel" id="aba-ia">
    <div class="painel ia">
      <div class="painel-cab"><h2>Parecer do agente de IA</h2>${iaOk ? `<span class="sub">${esc(d.ia.provedor || "")} · ${esc(d.ia.modelo)}</span>` : ""}</div>
      <div class="painel-corpo">${parecerIA(d.ia)}</div>
    </div>
  </div>

  <div class="aba-painel" id="aba-cookies">${cookiesRastreadores(d)}</div>`;

  $$("#resultado [data-aba]").forEach((b) => b.addEventListener("click", () => abrirAba(b.dataset.aba)));
  $("#resultado").hidden = false;
  $("#nav-resultado").classList.remove("desabilitado");
  $$("[data-nav]").forEach((x) => x.classList.toggle("ativo", x.id === "nav-resultado"));
  $("#resultado").scrollIntoView({ behavior: "smooth" });
}

function abrirAba(nome) {
  $$("#resultado [data-aba]").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
  $$("#resultado .aba-painel").forEach((p) => p.classList.toggle("ativa", p.id === "aba-" + nome));
}

function visaoGeral(d) {
  const r = d.resumo_campos;
  const cor = { ok: "var(--ok)", parcial: "var(--parcial)", falha: "var(--falha)" }[d.nivel];
  const circ = 2 * Math.PI * 72;
  return `
  <div class="grade g-topo">
    <div class="painel">
      <div class="painel-cab"><h2>Nota de conformidade</h2></div>
      <div class="painel-corpo nota">
        <div class="anel" role="img" aria-label="Nota ${d.score} de 100">
          <svg width="170" height="170" viewBox="0 0 170 170">
            <circle cx="85" cy="85" r="72" fill="none" stroke="var(--trilho)" stroke-width="13"/>
            <circle cx="85" cy="85" r="72" fill="none" stroke="${cor}" stroke-width="13" stroke-linecap="round"
                    stroke-dasharray="${(circ * d.score) / 100} ${circ}"/>
          </svg>
          <div class="valor"><b>${d.score}</b><span>de 100</span></div>
        </div>
        ${st(d.nivel, d.classificacao)}
        <div class="legenda-nota">≥ 80 adequado · 50–79 parcial · &lt; 50 baixa</div>
      </div>
    </div>
    <div class="painel">
      <div class="painel-cab"><h2>Adequação por categoria</h2><span class="sub">nota 0–100 · peso na nota final</span></div>
      <div class="painel-corpo barras">
        ${Object.values(d.categorias).map((c) => `
          <div class="barra-linha ${c.nota === null ? "na" : ""}" title="${esc(c.nome)}: ${c.nota ?? "não se aplica"} (${c.regras} regras)">
            <div class="rot">${esc(c.nome)}<small>${esc(c.base)} · peso ${c.peso}%</small></div>
            <div class="trilho"><div class="preench" style="width:${c.nota ?? 0}%"></div></div>
            <div class="num">${c.nota ?? "n/a"}</div>
          </div>`).join("")}
      </div>
    </div>
  </div>

  <div class="kpis">
    ${kpi("Campos analisados", r.total)}
    ${kpi("Campos excessivos", r.excessivos)}
    ${kpi("Dados sensíveis", r.sensiveis)}
    ${kpi("Campos obrigatórios", r.obrigatorios)}
    ${kpi("Cookies", d.cookies.length)}
    ${kpi("Rastreadores", d.rastreadores.length)}
  </div>

  <div class="grade g-2">
    <div class="painel">
      <div class="painel-cab"><h2>Verificações objetivas</h2></div>
      <ul class="lista-st">
        ${d.verificacoes_objetivas.map((v) => `<li><span>${esc(v.item)}</span><span class="sim-nao">${v.valor ? "SIM" : "NÃO"}</span></li>`).join("")}
      </ul>
    </div>
    <div class="painel">
      <div class="painel-cab"><h2>Principais riscos</h2></div>
      <div class="riscos">${riscos(d)}</div>
    </div>
  </div>
  ${resumoIA(d.ia)}`;
}

// Cartão de destaque do agente de IA na visão geral
function resumoIA(ia) {
  if (!ia || !ia.disponivel) {
    return `<div class="painel ia-resumo ia-off"><div class="painel-corpo">
      <span class="motor-etiqueta">Agente de IA</span>
      <p class="aviso" style="margin:4px 0 0">${esc(ia?.motivo || "Esta análise foi feita sem o agente de IA.")}
      Marque “Incluir parecer contextual do agente de IA” e analise novamente.</p></div></div>`;
  }
  return `<div class="painel ia-resumo">
    <div class="painel-cab"><h2>Interpretação do agente de IA</h2><span class="sub">${esc(ia.provedor || "")} · ${esc(ia.modelo)}</span></div>
    <div class="painel-corpo">
      <div class="destaque-ia"><span class="rotulo">Finalidade inferida</span>${esc(ia.finalidade_inferida)}</div>
      <p class="texto">${esc(ia.resumo.split(/\n+/)[0])}</p>
      <a href="#" onclick="abrirAba('ia');return false">Ver parecer completo, recomendações e pontos positivos →</a>
    </div>
  </div>`;
}

const kpi = (t, n) => `<div class="kpi"><span>${esc(t)}</span><b>${n}</b></div>`;

function riscos(d) {
  const lista = [...(d.ia?.disponivel ? d.ia.riscos.map((x) => ({ ...x, titulo: "", origem: "ia" })) : []), ...d.riscos];
  const ordem = { alto: 0, medio: 1, baixo: 2 };
  lista.sort((a, b) => ordem[a.nivel] - ordem[b.nivel]);
  if (!lista.length) return st("ok", "Nenhum risco relevante identificado.");
  const N = 6;
  return lista.slice(0, N).map((x) => `
    <div class="risco ${x.nivel}">
      <div class="t">${esc(x.titulo || x.descricao)} <span class="tag">${NIVEL_RISCO[x.nivel]}</span>
        <span class="tag">${x.origem === "ia" ? "IA" : "Regras"}</span></div>
      ${x.titulo ? `<div class="d">${esc(x.descricao)}</div>` : ""}
      <div class="a">${esc(x.artigo)}</div>
    </div>`).join("") +
    (lista.length > N ? `<p class="mais">+ ${lista.length - N} itens — veja a aba <a href="#" onclick="abrirAba('checklist');return false">Checklist LGPD</a>.</p>` : "");
}

function tabelaCampos(d) {
  if (!d.campos.length) return `<div class="painel-corpo aviso">Nenhum campo de dado pessoal encontrado.</div>`;
  const temIA = d.campos.some((c) => c.avaliacao_ia);
  return `<div class="tabela-wrap"><table class="tabela">
    <thead><tr><th>Campo</th><th>Dado identificado</th><th>Obrigatório</th><th>Motor de regras</th>${temIA ? "<th>IA</th>" : ""}<th class="col-just">Justificativa</th></tr></thead>
    <tbody>${d.campos.map((c) => `
      <tr class="${c.sensivel ? "sens" : ""}">
        <td><b>${esc(c.rotulo || c.nome || c.id)}</b><small>${esc(c.tipo_html)}${c.nome ? " · name=" + esc(c.nome) : ""}</small></td>
        <td>${esc(c.tipo_nome)}${c.sensivel ? `<small>⚠ dado sensível</small>` : ""}</td>
        <td>${c.obrigatorio ? "Sim" : "Não"}</td>
        <td>${aval(c.avaliacao)}</td>
        ${temIA ? `<td>${aval(c.avaliacao_ia)}</td>` : ""}
        <td>${esc(c.justificativa_ia || c.motivo)}</td>
      </tr>`).join("")}</tbody>
  </table></div>`;
}

function tabelaConsentimentos(d) {
  if (!d.consentimentos.length) return "";
  return `<div class="subtitulo">Caixas de consentimento</div>
    <div class="tabela-wrap"><table class="tabela">
    <thead><tr><th>Texto do aceite</th><th>Pré-marcada</th><th>Obrigatória</th><th>Marketing</th></tr></thead>
    <tbody>${d.consentimentos.map((c) => `<tr><td>${esc(c.texto)}</td><td>${c.marcado ? st("falha", "Sim") : st("ok", "Não")}</td>
      <td>${c.obrigatorio ? "Sim" : "Não"}</td><td>${c.marketing ? "Sim" : "Não"}</td></tr>`).join("")}</tbody></table></div>`;
}

function regrasPorCategoria(d) {
  return Object.entries(d.categorias).map(([k, c]) => {
    const rs = d.regras.filter((r) => r.categoria === k);
    if (!rs.length) return "";
    const falhas = rs.filter((r) => r.status === "falha").length;
    return `<details class="categoria" ${falhas ? "open" : ""}>
      <summary>
        <span><span class="chev">›</span> ${esc(c.nome)}<small>${esc(c.base)}</small></span>
        <span class="trilho"><span class="preench" style="display:block;width:${c.nota ?? 0}%"></span></span>
        <span class="num">${c.nota ?? "n/a"}</span>
      </summary>
      ${rs.map((r) => `
        <div class="regra">
          <div>${st(r.status)}</div>
          <div class="regra-corpo">
            <b>${esc(r.id)} · ${esc(r.titulo)}</b>
            <div class="det">${esc(r.detalhe)}</div>
            <div class="art">${esc(r.artigo)} · peso ${r.peso}</div>
            ${r.recomendacao && r.status !== "ok" && r.status !== "na" ? `<div class="rec"><b>Recomendação:</b> ${esc(r.recomendacao)}</div>` : ""}
          </div>
        </div>`).join("")}
    </details>`;
  }).join("");
}

function parecerIA(ia) {
  if (!ia || !ia.disponivel) return `<p class="aviso">${esc(ia?.motivo || "Análise por IA não realizada.")}</p>`;
  const lista = (arr) => (arr?.length ? `<ul>${arr.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "<p>—</p>");
  return `
    <div class="destaque-ia"><span class="rotulo">Finalidade inferida</span>${esc(ia.finalidade_inferida)}</div>
    ${ia.resumo.split(/\n+/).map((p) => `<p class="texto">${esc(p)}</p>`).join("")}
    <div class="grade g-2" style="margin:16px 0 0">
      <div><h3>Recomendações</h3>${lista(ia.recomendacoes)}</div>
      <div><h3>Pontos positivos</h3>${lista(ia.pontos_positivos)}</div>
    </div>
    <p class="aviso" style="margin:16px 0 0;font-size:.78rem">A nota numérica vem exclusivamente do motor de regras; o parecer da IA é complementar.</p>`;
}

function cookiesRastreadores(d) {
  const b = d.banner_cookies;
  const banner = b ? `
      <ul class="lista-st">
        <li><span>Aceitar</span>${b.aceitar ? st("ok", "Presente") : st("na", "Ausente")}</li>
        <li><span>Recusar / rejeitar</span>${b.recusar ? st("ok", "Presente") : st("falha", "Ausente")}</li>
        <li><span>Configurar preferências</span>${b.configurar ? st("ok", "Presente") : st("parcial", "Ausente")}</li>
      </ul>
      <div class="painel-corpo quebra" style="border-top:1px solid var(--borda)"><span class="rotulo">Texto do banner</span>
        <span class="texto">“${esc(b.texto.slice(0, 300))}”</span></div>`
    : `<div class="painel-corpo aviso">${d.cmp ? `Plataforma de consentimento ${esc(d.cmp)} detectada (banner carregado dinamicamente).` : "Nenhum banner de cookies detectado."}</div>`;

  const rastreadores = d.rastreadores.length
    ? `<ul class="lista-st">${d.rastreadores.map((t) => `<li><span>${esc(t.nome)}</span><small class="aviso">${esc(t.evidencia)}</small></li>`).join("")}</ul>`
    : `<div class="painel-corpo aviso">Nenhum rastreador conhecido carregado no primeiro acesso.</div>`;

  const cookies = d.cookies.length
    ? `<div class="tabela-wrap"><table class="tabela"><thead><tr><th>Cookie</th><th>Domínio</th><th>Origem</th><th>Validade</th><th>Secure</th></tr></thead>
      <tbody>${d.cookies.map((c) => `<tr><td>${esc(c.nome)}</td><td>${esc(c.dominio)}</td><td>${c.terceiro ? "Terceiro" : "Próprio"}</td>
        <td>${c.dias === null ? "Sessão" : esc(c.dias) + " dias"}</td><td>${c.secure ? "Sim" : "Não"}</td></tr>`).join("")}</tbody></table></div>`
    : `<div class="painel-corpo aviso">Nenhum cookie definido no primeiro acesso.</div>`;

  return `
  <div class="grade g-2">
    <div class="painel"><div class="painel-cab"><h2>Banner de cookies</h2></div>${banner}</div>
    <div class="painel"><div class="painel-cab"><h2>Rastreadores de terceiros</h2><span class="sub">carregados sem consentimento</span></div>${rastreadores}</div>
  </div>
  <div class="painel">
    <div class="painel-cab"><h2>Cookies no primeiro acesso</h2><span class="sub">${d.cookies.length} cookie(s)</span></div>
    ${cookies}
    ${d.dominios_terceiros?.length ? `<div class="painel-corpo quebra" style="border-top:1px solid var(--borda)">
      <span class="rotulo">Domínios de terceiros contactados</span><span class="texto">${d.dominios_terceiros.map(esc).join(" · ")}</span></div>` : ""}
  </div>`;
}

function imprimir() {
  $$("#resultado details").forEach((x) => (x.open = true));
  window.print();
}

function baixarJSON() {
  const blob = new Blob([JSON.stringify(relatorioAtual, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `analise-lgpd-${relatorioAtual.id}.json`;
  a.click();
}

// ------------------------------------------------------------------ histórico
async function carregarHistorico() {
  const itens = await (await fetch("/api/historico")).json();
  if (!itens.length) return;
  $("#historico").innerHTML = itens.map((h) => `
    <tr class="clicavel" data-id="${esc(h.id)}">
      <td>${new Date(h.data).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</td>
      <td class="quebra">${esc(urlCurta(h.url))}</td>
      <td class="dir"><b>${h.score}</b></td>
      <td>${st(h.nivel, { ok: "Adequado", parcial: "Parcial", falha: "Baixa" }[h.nivel])}</td>
      <td>${h.ia ? '<span class="tag">Com IA</span>' : '<span class="aviso">—</span>'}</td>
    </tr>`).join("");
  $$("#historico tr[data-id]").forEach((tr) =>
    tr.addEventListener("click", async () => mostrar(await (await fetch("/api/historico/" + tr.dataset.id)).json()))
  );
}
carregarHistorico();
