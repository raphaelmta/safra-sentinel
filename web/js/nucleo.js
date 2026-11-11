// Peças compartilhadas por todas as páginas: chamadas à API, filtros, formatação e pequenos componentes.

export const NIVEL = {
    alto: { rotulo: 'Risco alto', var: '--alto', raio: 6 },
    atencao: { rotulo: 'Atenção', var: '--atencao', raio: 5 },
    baixo: { rotulo: 'Risco baixo', var: '--baixo', raio: 3.5 },
};
export const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

// ------------------------------------------------------------------ API
export class ErroSessao extends Error {}

export async function api(caminho, opcoes = {}) {
    const resposta = await fetch(caminho, {
        credentials: 'same-origin',
        headers: opcoes.body ? { 'Content-Type': 'application/json' } : undefined,
        ...opcoes,
        body: opcoes.body ? JSON.stringify(opcoes.body) : undefined,
    });
    if (resposta.status === 401 && !caminho.startsWith('/api/login')) {
        window.dispatchEvent(new CustomEvent('sessao-expirada'));
        throw new ErroSessao('Sessão expirada. Entre novamente.');
    }
    if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => ({}));
        throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `Não foi possível concluir (erro ${resposta.status}).`);
    }
    return resposta.json();
}

// ------------------------------------------------------------- filtros
// Um único conjunto de filtros vale para todas as páginas e sobrevive ao recarregar.
const CHAVE_FILTROS = 'safra.filtros';
export const filtros = { ano: null, cultura: 'milho', uf: '', mun: null };
export let opcoes = null;

export async function carregarOpcoes() {
    opcoes = await api('/api/opcoes');
    try { Object.assign(filtros, JSON.parse(localStorage.getItem(CHAVE_FILTROS) || '{}')); } catch { /* sem armazenamento */ }
    if (!opcoes.anos.includes(Number(filtros.ano))) filtros.ano = opcoes.anos[0];
    if (!opcoes.culturas.some((c) => c.id === filtros.cultura)) filtros.cultura = opcoes.culturas[0].id;
    if (filtros.uf && !opcoes.ufs.some((u) => u.id === filtros.uf)) filtros.uf = '';
    filtros.ano = Number(filtros.ano);
    return opcoes;
}

export function definirFiltros(novos) {
    Object.assign(filtros, novos);
    if (filtros.ano != null) filtros.ano = Number(filtros.ano);
    if (filtros.mun != null && filtros.mun !== '') filtros.mun = Number(filtros.mun); else filtros.mun = null;
    try { localStorage.setItem(CHAVE_FILTROS, JSON.stringify(filtros)); } catch { /* sem armazenamento */ }
}

// Safras sem resultado oficial aparecem como "2026 (previsão)"
export const semResultado = (ano) => Boolean(opcoes?.anos_sem_resultado?.includes(Number(ano)));
export const opcoesAnos = () => opcoes.anos.map((a) => ({ id: a, nome: semResultado(a) ? `${a} (previsão)` : String(a) }));
export const textoReal = (v) => (v == null ? 'A divulgar' : (v ? 'Safra quebrou' : 'Safra normal'));
export const dataBr = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '—');
export const CHUVA = {
    muito_abaixo: { rotulo: 'Muito abaixo do normal', var: '--alto', raio: 6 },
    abaixo: { rotulo: 'Abaixo do normal', var: '--atencao', raio: 5 },
    normal: { rotulo: 'Dentro do normal', var: '--marca', raio: 4.5 },
    acima: { rotulo: 'Acima do normal', var: '--foco', raio: 4.5 },
    seca: { rotulo: 'Época normalmente seca', var: '--baixo', raio: 3.5 },
};

export const nomeCultura = (id) => opcoes?.culturas.find((c) => c.id === id)?.nome ?? id;
export const nomeUf = (id) => opcoes?.ufs.find((u) => u.id === id)?.nome ?? id;

// --------------------------------------------------------- formatação
export const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
export const inteiro = (v) => (v == null ? '—' : Math.round(v).toLocaleString('pt-BR'));
export const decimal = (v, casas = 1) => (v == null ? '—' : Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }));
export const reais = (v) => (v == null ? '—' : Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }));
export const cor = (variavel) => getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
export const selo = (nivel) => `<span class="selo ${nivel}">${NIVEL[nivel].rotulo}</span>`;
export const temaEscuro = () => document.documentElement.dataset.tema === 'escuro';

// *negrito* do WhatsApp → <b>, o resto como texto puro
export const formatarWhatsapp = (texto) => esc(texto).replace(/\*([^*\n]+)\*/g, '<b>$1</b>');

// ----------------------------------------------------------- componentes
export function avisar(texto) {
    const caixa = document.getElementById('avisos');
    const item = document.createElement('div');
    item.className = 'aviso';
    item.textContent = texto;
    caixa.append(item);
    setTimeout(() => item.remove(), 3200);
}

export async function copiar(texto, confirmacao = 'Copiado') {
    try {
        await navigator.clipboard.writeText(texto);
        avisar(confirmacao);
    } catch {
        avisar('Não foi possível copiar. Selecione o texto e copie manualmente.');
    }
}

export function abrirDialogo(titulo, html) {
    const dialogo = document.getElementById('dialogo');
    document.getElementById('dialogo-corpo').innerHTML = `
        <div class="dialogo-topo"><h2>${esc(titulo)}</h2>
            <button class="botao pequeno" data-fechar>Fechar</button></div>
        <div class="dialogo-conteudo">${html}</div>`;
    dialogo.querySelector('[data-fechar]').addEventListener('click', () => dialogo.close());
    dialogo.addEventListener('click', (e) => { if (e.target === dialogo) dialogo.close(); }, { once: true });
    dialogo.showModal();
    return dialogo;
}

export function htmlAviso(mensagens) {
    return `
        <div class="fone" aria-label="Simulação da conversa no WhatsApp">
            <div class="fone-topo"><img src="/img/marca.svg" alt=""><div>Safra Sentinela<small>conta comercial</small></div></div>
            <div class="fone-corpo">
                <div class="balao">${formatarWhatsapp(mensagens.whatsapp)}</div>
                <div class="balao audio" aria-label="Mensagem de áudio, ilustrativa"><i></i>0:32</div>
            </div>
        </div>
        <div class="linha-copiar">
            <span class="nota">Versão para WhatsApp</span>
            <button class="botao pequeno" data-copiar="whatsapp">Copiar texto</button>
        </div>
        <div>
            <div class="linha-copiar">
                <span class="nota">Versão SMS, para celular simples: <b class="num">${mensagens.sms.length}</b> de 160 caracteres</span>
                <button class="botao pequeno" data-copiar="sms">Copiar SMS</button>
            </div>
            <p class="sms">${esc(mensagens.sms)}</p>
        </div>`;
}

export function ligarCopiar(raiz, mensagens) {
    raiz.querySelectorAll('[data-copiar]').forEach((b) => b.addEventListener('click', () => {
        const tipo = b.dataset.copiar;
        copiar(mensagens[tipo], tipo === 'sms' ? 'SMS copiado' : 'Texto do WhatsApp copiado');
    }));
}

// Campo de busca de município com lista de sugestões (teclado e mouse).
export function buscaMunicipio(input, aoEscolher) {
    const caixa = input.closest('.busca');
    const lista = document.createElement('ul');
    lista.className = 'busca-lista';
    lista.setAttribute('role', 'listbox');
    lista.hidden = true;
    caixa.append(lista);
    let itens = [], ativo = -1, pedido = 0;

    const fechar = () => { lista.hidden = true; ativo = -1; };
    const escolher = (m) => { input.value = `${m.municipio} (${m.uf})`; fechar(); aoEscolher(m); };
    const pintar = () => {
        lista.innerHTML = itens.map((m, i) => `<li role="option" aria-selected="${i === ativo}" data-i="${i}">${esc(m.municipio)}<span>${esc(m.uf)}</span></li>`).join('')
            || '<li class="nota">Nenhum município do Semiárido com esse nome</li>';
        lista.hidden = false;
    };

    input.addEventListener('input', async () => {
        const termo = input.value.trim();
        if (termo.length < 2) { fechar(); return; }
        const meu = ++pedido;
        try {
            const achados = await api(`/api/municipios?q=${encodeURIComponent(termo)}`);
            if (meu !== pedido) return;
            itens = achados; ativo = achados.length ? 0 : -1; pintar();
        } catch { fechar(); }
    });
    input.addEventListener('keydown', (e) => {
        if (lista.hidden) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); ativo = Math.min(ativo + 1, itens.length - 1); pintar(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); ativo = Math.max(ativo - 1, 0); pintar(); }
        else if (e.key === 'Enter' && itens[ativo]) { e.preventDefault(); escolher(itens[ativo]); }
        else if (e.key === 'Escape') fechar();
    });
    lista.addEventListener('mousedown', (e) => {
        const li = e.target.closest('li[data-i]');
        if (li) { e.preventDefault(); escolher(itens[Number(li.dataset.i)]); }
    });
    input.addEventListener('blur', () => setTimeout(fechar, 120));
}

export function opcoesSelect(lista, atual, vazio) {
    return (vazio ? `<option value="">${esc(vazio)}</option>` : '')
        + lista.map((o) => {
            const id = o.id ?? o, nome = o.nome ?? o;
            return `<option value="${esc(id)}" ${String(id) === String(atual) ? 'selected' : ''}>${esc(nome)}</option>`;
        }).join('');
}

export function segmentado(nome, lista, atual) {
    return `<div class="segmentado" role="group" data-seg="${nome}">${lista.map((o) =>
        `<button type="button" data-valor="${esc(o.id)}" aria-pressed="${String(o.id) === String(atual)}">${esc(o.nome)}</button>`).join('')}</div>`;
}

export function ligarSegmentado(raiz, nome, aoMudar) {
    const grupo = raiz.querySelector(`[data-seg="${nome}"]`);
    grupo.addEventListener('click', (e) => {
        const botao = e.target.closest('button[data-valor]');
        if (!botao || botao.getAttribute('aria-pressed') === 'true') return;
        grupo.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b === botao)));
        aoMudar(botao.dataset.valor);
    });
}

export function navegar(rota, params = {}) {
    const validos = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));
    const consulta = new URLSearchParams(validos).toString();
    location.hash = `#/${rota}${consulta ? '?' + consulta : ''}`;
}
