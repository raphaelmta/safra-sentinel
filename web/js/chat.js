// Assistente: conversa sobre a base de risco, com respostas em texto, cartões, tabelas e séries.
import {
    api, copiar, definirFiltros, esc, formatarWhatsapp, navegar, nomeCultura, nomeUf, pct, selo, textoReal,
} from './nucleo.js';

const CHAVE = 'safra.conversa';
const TOPICOS = [
    'Qual o risco em Monteiro?',
    'Quais municípios têm maior risco na Paraíba?',
    'Compare Ceará e Bahia',
    'Como está a chuva agora no Semiárido?',
    'Histórico do Semiárido',
    'Como funciona o modelo?',
    'O que fazer em risco alto?',
];
let raiz, conversa, ocupado = false;

function carregarConversa() {
    try { return JSON.parse(sessionStorage.getItem(CHAVE)) || { itens: [], contexto: {} }; }
    catch { return { itens: [], contexto: {} }; }
}
function salvarConversa() {
    try { sessionStorage.setItem(CHAVE, JSON.stringify(conversa)); } catch { /* sem armazenamento */ }
}

export async function montar(conteudo, params) {
    raiz = conteudo;
    conversa = carregarConversa();
    raiz.innerHTML = `
        <div class="pagina-topo">
            <div>
                <h1>Assistente</h1>
                <p>Pergunte sobre o risco de um município, de um estado ou sobre o modelo. As respostas são calculadas na hora, com os mesmos números do painel.</p>
            </div>
            <button class="botao" id="c-nova">Nova conversa</button>
        </div>
        <div class="assistente">
            <section class="painel-bloco conversa" aria-label="Conversa">
                <div class="conversa-mensagens" id="c-mensagens" aria-live="polite"></div>
                <div class="conversa-entrada">
                    <div class="sugestoes" id="c-sugestoes"></div>
                    <form class="conversa-form" id="c-form">
                        <label class="pular" for="c-campo">Sua pergunta</label>
                        <input type="text" id="c-campo" maxlength="400" autocomplete="off"
                               placeholder="Ex.: qual o risco de feijão em Paulistana em 2023?">
                        <button class="botao primario" type="submit">Perguntar</button>
                    </form>
                </div>
            </section>
            <aside class="painel-bloco contexto-conversa">
                <div>
                    <h2>Sobre o que estamos falando</h2>
                    <p class="nota pequeno">O assistente lembra do último lugar, safra e cultura. Você pode dizer só “e o feijão?” ou “e em 2023?”.</p>
                </div>
                <dl id="c-contexto"></dl>
                <div>
                    <h2>Perguntas que funcionam bem</h2>
                    <div class="topicos">${TOPICOS.map((t) => `<button type="button" data-pergunta="${esc(t)}">${esc(t)}</button>`).join('')}</div>
                </div>
            </aside>
        </div>`;

    raiz.querySelector('#c-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const campo = raiz.querySelector('#c-campo');
        perguntar(campo.value);
        campo.value = '';
    });
    raiz.querySelector('#c-nova').addEventListener('click', () => {
        conversa = { itens: [], contexto: {} };
        salvarConversa();
        raiz.querySelector('#c-mensagens').innerHTML = '';
        saudar();
        raiz.querySelector('#c-campo').focus();
    });
    // um único ouvinte para todos os botões que disparam uma pergunta ou uma ação
    raiz.addEventListener('click', (e) => {
        const pergunta = e.target.closest('[data-pergunta]');
        if (pergunta) { perguntar(pergunta.dataset.pergunta); return; }
        const acao = e.target.closest('[data-rota]');
        if (acao) {
            const params2 = JSON.parse(acao.dataset.params || '{}');
            definirFiltros(Object.fromEntries(Object.entries(params2).filter(([k]) => ['ano', 'cultura', 'uf', 'mun'].includes(k))));
            navegar(acao.dataset.rota, params2);
            return;
        }
        const copia = e.target.closest('[data-copiar-texto]');
        if (copia) copiar(copia.dataset.copiarTexto);
    });

    if (conversa.itens.length) conversa.itens.forEach((i) => pintar(i, false));
    else saudar();
    pintarContexto();
    rolar(false);
    if (params.pergunta) {
        history.replaceState(null, '', '#/assistente'); // não repete a pergunta ao recarregar
        perguntar(params.pergunta);
    }
    raiz.querySelector('#c-campo').focus();
}

export function desmontar() { ocupado = false; }

function saudar() {
    const item = {
        de: 'assistente',
        texto: 'Olá! Sou o assistente do Safra Sentinela. Posso dizer o risco de quebra de um município, listar os de maior risco num estado, comparar estados e explicar como o modelo funciona.',
        blocos: [], acoes: [],
        sugestoes: ['Qual o risco em Monteiro?', 'Quais municípios têm maior risco na Paraíba?', 'Como funciona o modelo?'],
    };
    conversa.itens.push(item);
    pintar(item, false);
    salvarConversa();
}

async function perguntar(texto) {
    texto = (texto || '').trim();
    if (!texto || ocupado) return;
    ocupado = true;
    const minha = { de: 'usuario', texto };
    conversa.itens.push(minha);
    pintar(minha);
    raiz.querySelector('#c-sugestoes').innerHTML = '';

    const lista = raiz.querySelector('#c-mensagens');
    const espera = document.createElement('div');
    espera.className = 'msg';
    espera.innerHTML = '<div class="msg-texto digitando" aria-label="O assistente está respondendo"><i></i><i></i><i></i></div>';
    lista.append(espera);
    rolar();

    let item;
    try {
        const [r] = await Promise.all([
            api('/api/chat', { method: 'POST', body: { mensagem: texto, contexto: conversa.contexto } }),
            new Promise((ok) => setTimeout(ok, 280)), // evita o pisca-pisca do indicador
        ]);
        conversa.contexto = r.contexto || {};
        item = { de: 'assistente', texto: r.texto, blocos: r.blocos, acoes: r.acoes, sugestoes: r.sugestoes };
    } catch (ex) {
        item = { de: 'assistente', texto: `Não consegui responder agora. ${ex.message}`, blocos: [], acoes: [], sugestoes: [texto] };
    }
    espera.remove();
    if (!raiz.isConnected) { ocupado = false; return; }
    conversa.itens.push(item);
    if (conversa.itens.length > 60) conversa.itens = conversa.itens.slice(-60);
    pintar(item);
    pintarContexto();
    salvarConversa();
    ocupado = false;
}

// texto simples com **negrito**, parágrafos e listas
function formatar(texto) {
    const negrito = (t) => esc(t).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    return texto.split(/\n{2,}/).map((bloco) => {
        const linhas = bloco.split('\n');
        if (linhas.every((l) => /^- /.test(l))) return `<ul>${linhas.map((l) => `<li>${negrito(l.slice(2))}</li>`).join('')}</ul>`;
        if (linhas.every((l) => /^\d+\. /.test(l))) return `<ol>${linhas.map((l) => `<li>${negrito(l.replace(/^\d+\. /, ''))}</li>`).join('')}</ol>`;
        return `<p>${negrito(bloco).replace(/\n/g, '<br>')}</p>`;
    }).join('');
}

function htmlBloco(b) {
    if (b.tipo === 'kpis') {
        return `<div class="msg-bloco"><div class="kpis-chat">${b.itens.map((k) =>
            `<div><span>${esc(k.rotulo)}</span><b>${esc(k.valor)}</b><small>${esc(k.detalhe || '')}</small></div>`).join('')}</div></div>`;
    }
    if (b.tipo === 'tabela') {
        const celula = (c) => (c && typeof c === 'object' && c.nivel ? selo(c.nivel) : esc(c));
        return `<div class="msg-bloco"><div class="tabela-rolagem"><table class="dados">
            <thead><tr>${b.colunas.map((c) => `<th scope="col">${esc(c)}</th>`).join('')}</tr></thead>
            <tbody>${b.linhas.map((l, i) => `<tr ${b.perguntas ? `data-pergunta="${esc(b.perguntas[i])}" tabindex="0" title="Perguntar sobre este município"` : ''}>${l.map((c) => `<td>${celula(c)}</td>`).join('')}</tr>`).join('')}</tbody>
        </table></div></div>`;
    }
    if (b.tipo === 'municipio') {
        const d = b.dados;
        return `<div class="msg-bloco"><div class="dentro">
            <div class="detalhe-topo"><div><h3 style="font-size:1.15rem">${esc(d.municipio)} (${esc(d.uf)})</h3>
                <p class="nota pequeno">${esc(nomeCultura(d.cultura))}, safra ${d.ano}${d.estacao?.length ? `. Chuvas de ${esc(d.estacao[0])} a ${esc(d.estacao[3])}` : ''}</p></div>${selo(d.nivel)}</div>
            <div class="detalhe-numeros" style="margin-bottom:0">
                <div><span>Chance de quebra</span><b>${pct(d.prob)}</b></div>
                <div><span>Chuva da estação</span><b>${d.chuva_pct == null ? '—' : d.chuva_pct + '%'}</b></div>
                <div><span>Resultado real</span><b class="texto">${textoReal(d.quebra_real)}</b></div>
            </div></div></div>`;
    }
    if (b.tipo === 'serie') {
        const max = Math.max(...b.pontos.map((p) => p.valor), 1);
        const poucos = b.pontos.length <= 8;
        return `<div class="msg-bloco"><div class="dentro"><p class="nota pequeno">${esc(b.titulo)}</p>
            <div class="serie" role="img" aria-label="${esc(b.titulo)}: ${b.pontos.map((p) => `${p.rotulo}, ${p.valor}%`).join('; ')}">
                ${b.pontos.map((p) => `<div title="${esc(p.rotulo)}: ${p.valor}%${p.marca ? ' (' + esc(p.marca) + ')' : ''}">
                    <i class="${p.nivel}" style="height:${Math.max(2, (p.valor / max) * 100)}%" ${poucos || p.valor === max ? `data-v="${p.valor}%"` : ''}></i>
                    <em>${esc(p.marca)}</em>${esc(p.rotulo)}</div>`).join('')}
            </div></div></div>`;
    }
    if (b.tipo === 'mensagem') {
        return `<div class="msg-bloco"><div class="dentro" style="display:grid;gap:.75rem">
            <div class="fone"><div class="fone-corpo"><div class="balao">${formatarWhatsapp(b.whatsapp)}</div></div></div>
            <div class="linha-copiar"><span class="nota pequeno">SMS: ${b.sms.length} de 160 caracteres</span>
                <span><button class="botao pequeno" data-copiar-texto="${esc(b.whatsapp)}">Copiar WhatsApp</button>
                <button class="botao pequeno" data-copiar-texto="${esc(b.sms)}">Copiar SMS</button></span></div>
            <p class="sms">${esc(b.sms)}</p></div></div>`;
    }
    return '';
}

function pintar(item, rolarFim = true) {
    const lista = raiz.querySelector('#c-mensagens');
    const caixa = document.createElement('div');
    caixa.className = `msg ${item.de === 'usuario' ? 'usuario' : ''}`;
    if (item.de === 'usuario') {
        caixa.innerHTML = `<div class="msg-texto">${esc(item.texto)}</div>`;
    } else {
        const acoes = (item.acoes || []).map((a) =>
            `<button class="botao pequeno" data-rota="${esc(a.rota)}" data-params="${esc(JSON.stringify(a.params || {}))}">${esc(a.rotulo)}</button>`).join('');
        caixa.innerHTML = `<div class="msg-texto">${formatar(item.texto)}</div>
            ${(item.blocos || []).map(htmlBloco).join('')}
            ${acoes ? `<div class="msg-acoes">${acoes}</div>` : ''}`;
        raiz.querySelector('#c-sugestoes').innerHTML = (item.sugestoes || []).map((s) =>
            `<button type="button" data-pergunta="${esc(s)}">${esc(s)}</button>`).join('');
    }
    lista.append(caixa);
    caixa.querySelectorAll('tr[data-pergunta]').forEach((tr) => tr.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') perguntar(tr.dataset.pergunta);
    }));
    if (rolarFim) rolar();
}

function rolar(suave = true) {
    const lista = raiz.querySelector('#c-mensagens');
    lista.scrollTo({ top: lista.scrollHeight, behavior: suave ? 'smooth' : 'auto' });
}

function pintarContexto() {
    const c = conversa.contexto || {};
    const linhas = [
        ['Safra', c.ano],
        ['Cultura', c.cultura ? nomeCultura(c.cultura) : null],
        ['Estado', c.uf ? nomeUf(c.uf) : null],
    ].filter(([, v]) => v);
    raiz.querySelector('#c-contexto').innerHTML = linhas.length
        ? linhas.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('')
        : '<p class="nota pequeno">Ainda sem contexto. Faça a primeira pergunta.</p>';
}
