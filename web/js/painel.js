// Painel de risco: mapa, resumo da safra, lista de prioridades e detalhe do município.
import {
    CHUVA, NIVEL, abrirDialogo, api, avisar, buscaMunicipio, cor, dataBr, definirFiltros, esc, filtros, htmlAviso,
    inteiro, ligarCopiar, ligarSegmentado, navegar, nomeCultura, opcoes, opcoesAnos, opcoesSelect, pct, segmentado,
    selo, semResultado, temaEscuro, textoReal,
} from './nucleo.js';

const ORDEM = ['baixo', 'atencao', 'alto']; // os alertas são desenhados por cima
let raiz, mapa, camada, marcadores, dados, chuva = null, modo = 'risco', relogio = null, pedido = 0;
const visiveis = { alto: true, atencao: true, baixo: true };
const visiveisChuva = { muito_abaixo: true, abaixo: true, normal: true, acima: true, seca: true };

export async function montar(conteudo, params = {}) {
    raiz = conteudo;
    modo = params.modo === 'chuva' ? 'chuva' : 'risco';
    raiz.innerHTML = `
        <div class="pagina-topo">
            <div>
                <h1>Painel de risco</h1>
                <p>Onde a lavoura corre mais risco de render menos da metade do habitual. Escolha a safra e a cultura, e clique num município para ver o detalhe.</p>
            </div>
        </div>

        <form class="filtros" id="p-filtros" onsubmit="return false">
            <label class="campo">Safra<select id="p-ano">${opcoesSelect(opcoesAnos(), filtros.ano)}</select></label>
            <div class="campo">Cultura${segmentado('cultura', opcoes.culturas, filtros.cultura)}</div>
            <label class="campo">Estado<select id="p-uf">${opcoesSelect(opcoes.ufs, filtros.uf, 'Todo o Semiárido')}</select></label>
            <label class="campo cresce">Buscar município
                <span class="busca"><input type="search" id="p-busca" placeholder="Digite o nome" autocomplete="off"></span>
            </label>
            <a class="botao fim" id="p-exportar" download>Baixar lista em CSV</a>
        </form>

        <dl class="resumo" id="p-resumo" aria-live="polite"></dl>

        <div class="painel-grade">
            <section class="painel-bloco mapa-bloco" aria-label="Mapa de risco">
                <div class="bloco-topo">
                    ${segmentado('modo', [{ id: 'risco', nome: 'Risco da safra' }, { id: 'chuva', nome: 'Chuva dos últimos 90 dias' }], modo)}
                    <ul class="legenda" id="p-legenda" aria-label="Mostrar ou esconder grupos no mapa"></ul>
                </div>
                <div id="mapa"></div>
                <div class="mapa-rodape" id="p-chuva-status" aria-live="polite"></div>
            </section>

            <div class="painel-lado">
                <section class="painel-bloco" id="p-detalhe" aria-live="polite"></section>
                <section class="painel-bloco">
                    <div class="bloco-topo"><h2>Prioridades de visita</h2><span class="nota pequeno" id="p-contagem"></span></div>
                    <div class="bloco-corpo" style="padding-inline:0;padding-bottom:0">
                        <ol class="ranking" id="p-ranking"></ol>
                    </div>
                </section>
            </div>
        </div>`;

    raiz.querySelector('#p-ano').addEventListener('change', (e) => { definirFiltros({ ano: e.target.value }); carregar(); });
    raiz.querySelector('#p-uf').addEventListener('change', (e) => { definirFiltros({ uf: e.target.value, mun: null }); carregar(true); });
    ligarSegmentado(raiz, 'cultura', (v) => { definirFiltros({ cultura: v }); carregar(); });
    buscaMunicipio(raiz.querySelector('#p-busca'), (m) => {
        // se o município está fora do estado filtrado, o filtro de estado acompanha a busca
        if (filtros.uf && filtros.uf !== m.uf) {
            definirFiltros({ uf: m.uf, mun: m.cod_mun });
            raiz.querySelector('#p-uf').value = m.uf;
            carregar();
        } else {
            selecionar(m.cod_mun, true);
        }
    });
    raiz.querySelector('#p-legenda').addEventListener('click', (e) => {
        const botao = e.target.closest('button[data-nivel]');
        if (!botao) return;
        const grupo = modo === 'chuva' ? visiveisChuva : visiveis;
        grupo[botao.dataset.nivel] = !grupo[botao.dataset.nivel];
        botao.setAttribute('aria-pressed', String(grupo[botao.dataset.nivel]));
        desenharMapa(false);
    });
    ligarSegmentado(raiz, 'modo', (v) => { modo = v; desenharLegenda(); desenharMapa(false); });
    raiz.querySelector('#p-chuva-status').addEventListener('click', (e) => {
        if (e.target.closest('#p-atualizar-chuva')) atualizarChuva();
    });

    criarMapa();
    desenharLegenda();
    carregarChuva();
    await carregar(true);
}

export function desmontar() {
    clearTimeout(relogio);
    mapa?.remove();
    mapa = null; dados = null;
}

function desenharLegenda() {
    const itens = modo === 'chuva' ? CHUVA : NIVEL;
    const grupo = modo === 'chuva' ? visiveisChuva : visiveis;
    raiz.querySelector('#p-legenda').innerHTML = Object.entries(itens).map(([id, n]) =>
        `<li><button type="button" data-nivel="${id}" aria-pressed="${grupo[id]}"><span class="ponto" style="width:.7rem;height:.7rem;background:var(${n.var})"></span>${n.rotulo}</button></li>`).join('');
}

// ---- chuva recente (quase em tempo real)
async function carregarChuva() {
    try {
        chuva = await api('/api/clima/mapa');
        const status = await api('/api/clima/status');
        if (!mapa) return;
        pintarStatusChuva(status);
        if (modo === 'chuva') desenharMapa(false);
        if (status.atualizando) acompanharAtualizacao();
    } catch { /* o painel de risco segue funcionando sem a chuva recente */ }
}

function pintarStatusChuva(s) {
    const caixa = raiz.querySelector('#p-chuva-status');
    if (!caixa) return;
    if (s.atualizando) {
        caixa.innerHTML = `<span>Buscando a chuva mais recente na NASA: ${s.feitas} de ${s.total} pontos…</span>`;
        return;
    }
    const meta = s.meta;
    caixa.innerHTML = `
        <span>${meta ? `Chuva medida por satélite até <b>${dataBr(meta.dados_ate)}</b> (a NASA publica com cerca de 3 dias de atraso; os dias mais recentes são preliminares).`
            : 'Ainda não há dados de chuva recente.'}${s.erro ? ` ${esc(s.erro)}` : ''}</span>
        <button class="botao pequeno" id="p-atualizar-chuva" type="button">Atualizar chuva</button>`;
}

async function atualizarChuva() {
    try {
        const r = await api('/api/clima/atualizar', { method: 'POST' });
        if (!r.iniciada && !r.atualizando) { avisar(r.motivo || 'Os dados já estão atualizados.'); return; }
        pintarStatusChuva({ ...r, atualizando: true });
        acompanharAtualizacao();
    } catch (ex) { avisar(ex.message); }
}

function acompanharAtualizacao() {
    clearTimeout(relogio);
    relogio = setTimeout(async () => {
        if (!mapa) return;
        try {
            const s = await api('/api/clima/status');
            pintarStatusChuva(s);
            if (s.atualizando) { acompanharAtualizacao(); return; }
            if (s.erro) avisar(s.erro); else avisar('Chuva atualizada');
            await carregarChuva();
            if (filtros.mun) selecionar(filtros.mun, false);
        } catch { /* tenta de novo na próxima ação do usuário */ }
    }, 2000);
}

function criarMapa() {
    mapa = L.map('mapa', { preferCanvas: true, minZoom: 4, maxZoom: 11 }).setView([-10.5, -40.5], 6);
    const estilo = temaEscuro() ? 'World_Dark_Gray' : 'World_Light_Gray';
    const base = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas';
    L.tileLayer(`${base}/${estilo}_Base/MapServer/tile/{z}/{y}/{x}`, {
        attribution: 'Mapa base © Esri, HERE, Garmin, © OpenStreetMap',
    }).addTo(mapa);
    L.tileLayer(`${base}/${estilo}_Reference/MapServer/tile/{z}/{y}/{x}`, { opacity: 0.85 }).addTo(mapa);
    camada = L.layerGroup().addTo(mapa);
    marcadores = new Map();
}

async function carregar(enquadrar = false) {
    const meu = ++pedido;
    const consulta = new URLSearchParams({ ano: filtros.ano, cultura: filtros.cultura });
    if (filtros.uf) consulta.set('uf', filtros.uf);
    raiz.querySelector('#p-exportar').href = `/api/exportar.csv?${consulta}`;
    try {
        const resposta = await api(`/api/risco?${consulta}`);
        if (meu !== pedido || !mapa) return;
        dados = resposta;
    } catch (ex) {
        if (meu === pedido) avisar(ex.message);
        return;
    }
    desenharResumo();
    desenharMapa(enquadrar);
    desenharRanking();
    const existe = dados.municipios.some((m) => m.cod_mun === filtros.mun);
    const alvo = existe ? filtros.mun : dados.municipios[0]?.cod_mun;
    if (alvo) selecionar(alvo, false); else detalheVazio();
}

function desenharResumo() {
    const r = dados.resumo;
    const parte = (n) => (r.safras ? pct(n / r.safras) : '—');
    raiz.querySelector('#p-resumo').innerHTML = `
        <div><dt>Em risco alto</dt><dd><strong>${inteiro(r.alto)}</strong><span>${parte(r.alto)} dos ${inteiro(r.safras)} municípios com plantio</span></dd></div>
        <div><dt>Em atenção</dt><dd><strong>${inteiro(r.atencao)}</strong><span>risco acima do normal, ainda sem alerta</span></dd></div>
        <div><dt>Chuva da estação</dt><dd><strong>${r.chuva_media_pct == null ? '—' : r.chuva_media_pct + '%'}</strong><span>do normal, na média dos municípios</span></dd></div>
        ${semResultado(dados.ano) ? `<div><dt>Resultado oficial</dt><dd><strong>A divulgar</strong>
            <span>previsão atual; o IBGE publica o resultado desta safra em ${dados.ano + 1}</span></dd></div>`
        : `<div><dt>Conferência com o resultado real</dt><dd><strong>${r.quebras_reais ? `${inteiro(r.quebras_avisadas)} de ${inteiro(r.quebras_reais)}` : '—'}</strong>
            <span>${r.quebras_reais ? `quebras avisadas; ${pct(r.precisao)} dos alertas se confirmaram` : 'nenhuma quebra registrada neste filtro'}</span></dd></div>`}`;
}

function desenharMapa(enquadrar) {
    camada.clearLayers();
    marcadores = new Map();
    const borda = temaEscuro() ? '#0e1612' : '#ffffff';
    const emChuva = modo === 'chuva' && chuva;
    const ordemChuva = ['seca', 'acima', 'normal', 'abaixo', 'muito_abaixo'];
    const grupoDe = (m) => (emChuva ? chuva.municipios[m.cod_mun]?.classe_90d : m.nivel);
    const lista = dados.municipios.filter((m) => {
        const g = grupoDe(m);
        return g && (emChuva ? visiveisChuva[g] : visiveis[g]);
    }).sort((a, b) => (emChuva ? ordemChuva.indexOf(grupoDe(a)) - ordemChuva.indexOf(grupoDe(b))
        : ORDEM.indexOf(a.nivel) - ORDEM.indexOf(b.nivel)));
    for (const m of lista) {
        const c = emChuva ? chuva.municipios[m.cod_mun] : null;
        const n = emChuva ? CHUVA[c.classe_90d] : NIVEL[m.nivel];
        const discreto = emChuva ? c.classe_90d === 'seca' : m.nivel === 'baixo';
        const marcador = L.circleMarker([m.lat, m.lon], {
            radius: n.raio, color: borda, weight: 1, fillColor: cor(n.var), fillOpacity: discreto ? 0.7 : 0.95,
        });
        marcador.bindTooltip(emChuva
            ? `<b>${esc(m.municipio)} (${esc(m.uf)})</b><br>${Math.round(c.chuva_90d)} mm em 90 dias`
                + (c.pct_90d == null ? '<br>Época normalmente seca' : `: ${c.pct_90d}% do normal`)
                + `<br>${c.dias_sem_chuva} dias seguidos sem chuva`
            : `<b>${esc(m.municipio)} (${esc(m.uf)})</b><br>${n.rotulo}: ${pct(m.prob)} de chance de quebra`
                + (m.chuva_pct == null ? '' : `<br>Chuva da estação: ${m.chuva_pct}% do normal`),
            { className: 'dica', direction: 'top', offset: [0, -4] });
        marcador.on('click', () => selecionar(m.cod_mun, false));
        marcador.addTo(camada);
        marcadores.set(m.cod_mun, marcador);
    }
    if (enquadrar && dados.municipios.length) {
        mapa.fitBounds(L.latLngBounds(dados.municipios.map((m) => [m.lat, m.lon])), { padding: [24, 24] });
    }
    if (filtros.mun) destacar(filtros.mun);
}

function desenharRanking() {
    const lista = raiz.querySelector('#p-ranking');
    const topo = dados.municipios.slice(0, 40);
    raiz.querySelector('#p-contagem').textContent = topo.length
        ? `os ${topo.length} de maior risco, de ${inteiro(dados.municipios.length)}` : '';
    if (!topo.length) {
        lista.innerHTML = '<li class="vazio">Nenhum município com plantio neste filtro. Tente outra cultura ou outro estado.</li>';
        return;
    }
    lista.innerHTML = topo.map((m, i) => `
        <li><button type="button" data-cod="${m.cod_mun}">
            <span class="ordem">${i + 1}</span>
            <span class="nome">${esc(m.municipio)} <small>${esc(m.uf)}</small></span>
            <span class="barra-risco" title="${NIVEL[m.nivel].rotulo}"><i style="--v:${Math.round(m.prob * 100)}%;--cor:var(${NIVEL[m.nivel].var})"></i>${pct(m.prob)}</span>
        </button></li>`).join('');
    lista.querySelectorAll('button').forEach((b) => {
        const codigo = Number(b.dataset.cod);
        b.addEventListener('click', () => selecionar(codigo, true));
        // passar o mouse na lista realça o ponto no mapa
        b.addEventListener('mouseenter', () => marcadores.get(codigo)?.openTooltip());
        b.addEventListener('mouseleave', () => marcadores.get(codigo)?.closeTooltip());
    });
}

function destacar(codigo) {
    const borda = temaEscuro() ? '#0e1612' : '#ffffff';
    marcadores.forEach((m) => m.setStyle({ color: borda, weight: 1 }));
    const marcador = marcadores.get(codigo);
    if (marcador) marcador.setStyle({ color: temaEscuro() ? '#ffffff' : '#14231b', weight: 3 }).bringToFront();
    return marcador;
}

async function selecionar(codigo, centralizar) {
    definirFiltros({ mun: codigo });
    const marcador = destacar(codigo);
    if (marcador && centralizar) mapa.flyTo(marcador.getLatLng(), Math.max(mapa.getZoom(), 8), { duration: 0.6 });
    raiz.querySelectorAll('#p-ranking button').forEach((b) => {
        const atual = Number(b.dataset.cod) === codigo;
        b.setAttribute('aria-current', String(atual));
        if (atual && centralizar) b.scrollIntoView({ block: 'nearest' });
    });
    try {
        const d = await api(`/api/municipio/${codigo}?ano=${filtros.ano}&cultura=${filtros.cultura}`);
        if (filtros.mun === codigo && mapa) desenharDetalhe(d);
    } catch (ex) {
        raiz.querySelector('#p-detalhe').innerHTML = `<div class="bloco-corpo"><p class="vazio">${esc(ex.message)}</p></div>`;
    }
}

function htmlChuvaAgora(c) {
    if (!c) return '';
    const max = Math.max(...c.serie.map((p) => p.mm), 5);
    const comparar = (pctv, normal) => (pctv == null ? `normal: ${Math.round(normal)} mm (época seca)` : `${pctv}% do normal`);
    return `
        <div class="chuva-agora">
            <div class="chuva-agora-topo"><h3>Chuva agora</h3><span class="nota pequeno">medida até ${dataBr(c.dados_ate)}</span></div>
            <div class="detalhe-numeros">
                <div><span>Últimos 30 dias</span><b>${Math.round(c.chuva_30d)} mm</b><small>${comparar(c.pct_30d, c.normal_30d)}</small></div>
                <div><span>Últimos 90 dias</span><b>${Math.round(c.chuva_90d)} mm</b><small>${comparar(c.pct_90d, c.normal_90d)}</small></div>
                <div><span>Sem chuva há</span><b>${c.dias_sem_chuva}${c.dias_sem_chuva_no_limite ? '+' : ''} dias</b><small>seguidos</small></div>
            </div>
            <div class="chuva-dias" role="img" aria-label="Chuva de cada dia nos últimos 90 dias. Total: ${Math.round(c.chuva_90d)} milímetros.">
                ${c.serie.map((p) => `<i style="height:${p.mm < 0.1 ? 0 : Math.max(4, (p.mm / max) * 100)}%" title="${dataBr(p.data)}: ${p.mm.toLocaleString('pt-BR')} mm"></i>`).join('')}
            </div>
            <div class="chuva-dias-eixo"><span>${dataBr(c.serie[0].data)}</span><span>cada barra é um dia</span><span>${dataBr(c.serie.at(-1).data)}</span></div>
        </div>`;
}

function detalheVazio() {
    raiz.querySelector('#p-detalhe').innerHTML = '<div class="bloco-corpo"><p class="vazio">Nenhum município para mostrar neste filtro.</p></div>';
}

function desenharDetalhe(d) {
    const caixa = raiz.querySelector('#p-detalhe');
    caixa.innerHTML = `
        <div class="bloco-corpo" style="padding-top:1.1rem">
            <div class="detalhe-topo">
                <div><h2>${esc(d.municipio)}</h2><p class="nota">${esc(d.uf)}, ${esc(nomeCultura(d.cultura).toLowerCase())}, safra ${d.ano}</p></div>
                ${selo(d.nivel)}
            </div>
            <div class="detalhe-numeros">
                <div><span>Chance de quebra</span><b>${pct(d.prob)}</b><small>alerta a partir de ${pct((opcoes.limiares[d.ano] || {}).alto)}</small></div>
                <div><span>Chuva da estação</span><b>${d.chuva_pct == null ? '—' : d.chuva_pct + '%'}</b><small>do normal</small></div>
                <div><span>Resultado real</span><b class="texto">${textoReal(d.quebra_real)}</b></div>
            </div>
            <p class="nota pequeno">Risco estimado em cada safra. Clique num ano para ver o mapa daquela safra.</p>
            <div class="safras">
                ${d.historico.map((h) => `
                    <button type="button" data-ano="${h.ano}" aria-pressed="${h.ano === d.ano}"
                            title="${h.ano}: ${NIVEL[h.nivel].rotulo}, ${pct(h.prob)}. ${h.quebra_real == null ? 'Resultado ainda não divulgado.' : (h.quebra_real ? 'A safra quebrou.' : 'Safra normal.')}">
                        ${h.ano}<span class="ponto ${h.nivel}"></span><b>${pct(h.prob)}</b><em class="${h.quebra_real == null ? 'previsao' : ''}">${h.quebra_real == null ? 'previsão' : (h.quebra_real ? 'quebrou' : '')}</em>
                    </button>`).join('')}
            </div>
            ${htmlChuvaAgora(d.chuva_recente)}
            <div class="detalhe-acoes">
                <button class="botao primario pequeno" id="p-ver-aviso">Ver aviso ao agricultor</button>
                <button class="botao pequeno" id="p-perguntar">Perguntar ao assistente</button>
            </div>
        </div>`;
    caixa.querySelectorAll('.safras button').forEach((b) => b.addEventListener('click', () => {
        definirFiltros({ ano: b.dataset.ano });
        raiz.querySelector('#p-ano').value = b.dataset.ano;
        carregar();
    }));
    caixa.querySelector('#p-ver-aviso').addEventListener('click', () => {
        const dialogo = abrirDialogo(`Aviso para ${d.municipio} (${d.uf})`, htmlAviso(d.mensagens));
        ligarCopiar(dialogo, d.mensagens);
    });
    caixa.querySelector('#p-perguntar').addEventListener('click', () =>
        navegar('assistente', { pergunta: `Qual o risco em ${d.municipio} ${d.uf}?` }));
}
