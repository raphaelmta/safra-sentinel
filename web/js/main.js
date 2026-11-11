// Entrada (login), sessão, navegação entre páginas e preferências.
import { api, avisar, carregarOpcoes, definirFiltros } from './nucleo.js';

const PAGINAS = {
    painel: () => import('./painel.js'),
    analises: () => import('./analises.js'),
    assistente: () => import('./chat.js'),
    utilidades: () => import('./utilidades.js'),
};
const TITULOS = { painel: 'Painel de risco', analises: 'Análises', assistente: 'Assistente', utilidades: 'Utilidades' };

const el = (id) => document.getElementById(id);
let paginaAtual = null;
let usuario = null;

// ------------------------------------------------------------- logo FIAP
// Usa web/img/fiap-logo.svg (ou .png) quando o arquivo oficial existir; senão, escreve "FIAP".
function montarLogoFiap() {
    document.querySelectorAll('[data-fiap]').forEach((caixa) => {
        const texto = () => { caixa.innerHTML = '<span class="fiap-texto" role="img" aria-label="FIAP">FIAP</span>'; };
        const tentar = (arquivos) => {
            if (!arquivos.length) { texto(); return; }
            const img = new Image();
            img.alt = 'FIAP';
            img.onload = () => caixa.replaceChildren(img);
            img.onerror = () => tentar(arquivos.slice(1));
            img.src = arquivos[0];
        };
        tentar(['/img/fiap-logo.svg', '/img/fiap-logo.png']);
    });
}

// ----------------------------------------------------------- preferências
function preferencias() {
    try { return JSON.parse(localStorage.getItem('safra.preferencias') || '{}'); } catch { return {}; }
}
function salvarPreferencia(chave, valor) {
    const p = { ...preferencias(), [chave]: valor };
    try { localStorage.setItem('safra.preferencias', JSON.stringify(p)); } catch { /* sem armazenamento */ }
}
function pintarPreferencias() {
    const raiz = document.documentElement;
    document.querySelectorAll('[data-tema-opcao]').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.temaOpcao === raiz.dataset.tema)));
    document.querySelectorAll('[data-texto-opcao]').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.textoOpcao === (raiz.dataset.texto || 'normal'))));
}
function ligarPreferencias() {
    document.querySelectorAll('[data-tema-opcao]').forEach((b) => b.addEventListener('click', () => {
        document.documentElement.dataset.tema = b.dataset.temaOpcao;
        salvarPreferencia('tema', b.dataset.temaOpcao);
        pintarPreferencias();
        rotear(); // mapas e gráficos leem as cores do tema ao serem montados
    }));
    document.querySelectorAll('[data-texto-opcao]').forEach((b) => b.addEventListener('click', () => {
        if (b.dataset.textoOpcao === 'normal') delete document.documentElement.dataset.texto;
        else document.documentElement.dataset.texto = b.dataset.textoOpcao;
        salvarPreferencia('texto', b.dataset.textoOpcao);
        pintarPreferencias();
    }));
    pintarPreferencias();
}

// ------------------------------------------------------------------ entrada
async function desenharTerritorio() {
    const tela = el('entrada-mapa');
    let dados;
    try { dados = await api('/api/publico/pontos'); } catch { return; }
    const cores = { a: '#e2573f', t: '#e8a317', b: '#5d6f65' };
    const raios = { a: 3.2, t: 2.6, b: 1.8 };
    const lons = dados.pontos.map((p) => p[0]), lats = dados.pontos.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];

    const pintar = () => {
        const caixa = tela.getBoundingClientRect();
        if (!caixa.width) return;
        const dpr = window.devicePixelRatio || 1;
        tela.width = caixa.width * dpr; tela.height = caixa.height * dpr;
        const c = tela.getContext('2d');
        c.scale(dpr, dpr);
        // o território ocupa a metade direita do painel, sem cobrir o texto
        const alturaUtil = caixa.height * 0.9;
        const escala = Math.min(alturaUtil / (y1 - y0), (caixa.width * 0.62) / (x1 - x0));
        const largura = (x1 - x0) * escala, altura = (y1 - y0) * escala;
        const dx = caixa.width - largura - caixa.width * 0.05, dy = (caixa.height - altura) / 2;
        for (const tipo of ['b', 't', 'a']) {
            c.fillStyle = cores[tipo];
            c.globalAlpha = tipo === 'b' ? 0.7 : 0.92;
            for (const [lon, lat, n] of dados.pontos) {
                if (n !== tipo) continue;
                c.beginPath();
                c.arc(dx + (lon - x0) * escala, dy + (y1 - lat) * escala, raios[tipo], 0, Math.PI * 2);
                c.fill();
            }
        }
    };
    pintar();
    new ResizeObserver(pintar).observe(tela);
    el('entrada-fato').textContent =
        `Cada ponto é um município do Semiárido. Na safra de milho de ${dados.ano}, ${dados.alto.toLocaleString('pt-BR')} dos ${dados.municipios.toLocaleString('pt-BR')} com plantio estavam em risco alto de quebra.`;
}

function mostrarEntrada() {
    el('plataforma').hidden = true;
    el('tela-entrada').hidden = false;
    document.title = 'Entrar · Safra Sentinela';
    desenharTerritorio();
    el('login-email').focus();
}

function ligarEntrada() {
    const form = el('form-login'), erro = el('login-erro');
    const falhar = (texto) => { erro.textContent = texto; erro.hidden = false; };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        erro.hidden = true;
        const email = el('login-email').value.trim(), senha = el('login-senha').value;
        if (!email || !senha) { falhar('Preencha o e-mail e a senha.'); return; }
        const botao = el('login-entrar');
        botao.disabled = true; botao.textContent = 'Entrando…';
        try {
            usuario = await api('/api/login', { method: 'POST', body: { email, senha } });
            form.reset();
            await abrirPlataforma();
        } catch (ex) {
            falhar(ex.message);
            el('login-senha').select();
        } finally {
            botao.disabled = false; botao.textContent = 'Entrar';
        }
    });
    el('login-visitante').addEventListener('click', async () => {
        erro.hidden = true;
        try {
            usuario = await api('/api/login/visitante', { method: 'POST' });
            await abrirPlataforma();
        } catch (ex) { falhar(ex.message); }
    });
    el('login-ver').addEventListener('click', () => {
        const campo = el('login-senha'), mostrar = campo.type === 'password';
        campo.type = mostrar ? 'text' : 'password';
        el('login-ver').textContent = mostrar ? 'Ocultar' : 'Mostrar';
        el('login-ver').setAttribute('aria-pressed', String(mostrar));
    });
}

// ---------------------------------------------------------------- plataforma
async function abrirPlataforma() {
    await carregarOpcoes();
    el('tela-entrada').hidden = true;
    el('plataforma').hidden = false;
    const partes = usuario.nome.split(/\s+/);
    el('usuario-iniciais').textContent = ((partes[0]?.[0] || '') + (partes.length > 1 ? partes.at(-1)[0] : '')).toUpperCase();
    el('usuario-nome').textContent = partes[0];
    el('menu-nome').textContent = usuario.nome;
    el('menu-papel').textContent = usuario.papel;
    if (!location.hash.startsWith('#/')) location.hash = '#/painel';
    else rotear();
}

function ligarMenu() {
    const botao = el('usuario-botao'), menu = el('usuario-menu');
    const fechar = () => { menu.hidden = true; botao.setAttribute('aria-expanded', 'false'); };
    botao.addEventListener('click', () => {
        menu.hidden = !menu.hidden;
        botao.setAttribute('aria-expanded', String(!menu.hidden));
    });
    document.addEventListener('click', (e) => { if (!e.target.closest('.menu-usuario')) fechar(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') fechar(); });
    el('sair').addEventListener('click', async () => {
        fechar();
        await api('/api/logout', { method: 'POST' }).catch(() => {});
        usuario = null;
        paginaAtual?.desmontar?.();
        paginaAtual = null;
        history.replaceState(null, '', location.pathname);
        mostrarEntrada();
    });
}

async function rotear() {
    if (!usuario) return;
    const [caminho, consulta] = location.hash.replace(/^#\//, '').split('?');
    const rota = PAGINAS[caminho] ? caminho : 'painel';
    const params = Object.fromEntries(new URLSearchParams(consulta || ''));
    // filtros vindos do endereço (links do assistente, por exemplo) passam a valer para todas as páginas
    const novos = {};
    for (const chave of ['ano', 'cultura', 'uf', 'mun']) if (chave in params) novos[chave] = params[chave];
    if (Object.keys(novos).length) definirFiltros(novos);

    document.querySelectorAll('.topo-nav a').forEach((a) => {
        if (a.dataset.rota === rota) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    document.title = `${TITULOS[rota]} · Safra Sentinela`;
    paginaAtual?.desmontar?.();
    const conteudo = el('conteudo');
    conteudo.innerHTML = '<p class="carregando">Carregando…</p>';
    try {
        paginaAtual = await PAGINAS[rota]();
        await paginaAtual.montar(conteudo, params);
    } catch (ex) {
        if (usuario) conteudo.innerHTML = `<p class="vazio">Não foi possível abrir esta página. ${ex.message}</p>`;
    }
    window.scrollTo(0, 0);
}

// --------------------------------------------------------------------- início
window.addEventListener('hashchange', rotear);
window.addEventListener('sessao-expirada', () => {
    if (!usuario) return;
    usuario = null;
    avisar('Sua sessão expirou. Entre novamente.');
    mostrarEntrada();
});

montarLogoFiap();
ligarEntrada();
ligarMenu();
ligarPreferencias();

try {
    usuario = await api('/api/eu');
    await abrirPlataforma();
} catch {
    usuario = null;
    mostrarEntrada();
}
