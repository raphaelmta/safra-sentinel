// Análises: histórico de quebras, alertas x resultado real, estados, chuva e simulador de limiar.
import {
    api, avisar, cor, decimal, definirFiltros, filtros, inteiro, ligarSegmentado, nomeUf, opcoes,
    opcoesSelect, pct, segmentado,
} from './nucleo.js';

const METRICAS_UF = [
    { id: 'taxa_quebra', nome: 'Safras que quebraram' },
    { id: 'recall', nome: 'Quebras avisadas' },
    { id: 'precisao', nome: 'Alertas confirmados' },
];
let raiz, dados, graficos = {}, cultura, metricaUf = 'taxa_quebra', medidaHist = 'taxa', limiar, pedido = 0;

export async function montar(conteudo) {
    raiz = conteudo;
    cultura = filtros.cultura;
    raiz.innerHTML = `
        <div class="pagina-topo">
            <div>
                <h1>Análises</h1>
                <p>O que os dados mostram sobre as quebras de safra e sobre o acerto do modelo. Os gráficos respondem aos filtros, e clicar num estado filtra todos os outros.</p>
            </div>
        </div>
        <form class="filtros" onsubmit="return false">
            <div class="campo">Cultura${segmentado('cultura', [...opcoes.culturas, { id: '', nome: 'As duas' }], cultura)}</div>
            <label class="campo">Estado<select id="a-uf">${opcoesSelect(opcoes.ufs, filtros.uf, 'Todo o Semiárido')}</select></label>
            <button type="button" class="chip-filtro" id="a-limpar" hidden></button>
        </form>

        <div class="analises-grade">
            <section class="painel-bloco largo">
                <div class="bloco-topo">
                    <div><h2>Quebras de safra desde 2003</h2><p class="nota" id="a-hist-nota"></p></div>
                    ${segmentado('medida', [{ id: 'taxa', nome: 'Lavouras com quebra' }, { id: 'producao', nome: 'Produção' }], medidaHist)}
                </div>
                <div class="bloco-corpo"><div class="grafico alto-g"><canvas id="g-hist" role="img"></canvas></div></div>
            </section>

            <section class="painel-bloco">
                <div class="bloco-topo"><div><h2>Alertas e quebras reais</h2><p class="nota" id="a-teste-nota">Parte das lavouras, em cada safra</p></div></div>
                <div class="bloco-corpo"><div class="grafico"><canvas id="g-teste" role="img"></canvas></div></div>
            </section>

            <section class="painel-bloco">
                <div class="bloco-topo"><div><h2>Menos chuva, mais quebras</h2><p class="nota">Lavouras que quebraram, por faixa de chuva da estação (% do normal)</p></div></div>
                <div class="bloco-corpo"><div class="grafico"><canvas id="g-chuva" role="img"></canvas></div></div>
            </section>

            <section class="painel-bloco largo">
                <div class="bloco-topo">
                    <div><h2>Comparação entre estados</h2><p class="nota">Safras já conferidas, de 2020 a 2025. Clique numa barra para filtrar a página por aquele estado.</p></div>
                    <label class="campo" style="min-width:13rem">Medida<select id="a-metrica">${opcoesSelect(METRICAS_UF, metricaUf)}</select></label>
                </div>
                <div class="bloco-corpo"><div class="grafico alto-g"><canvas id="g-uf" role="img"></canvas></div></div>
            </section>

            <section class="painel-bloco largo">
                <div class="bloco-topo">
                    <div><h2>Simulador de limiar</h2>
                        <p class="nota">O alerta sai quando a probabilidade de quebra passa de um limite. Como a quebra é rara (cerca de 16% das lavouras), o limite fica bem abaixo de 50%. Mova-o e veja a troca: avisar mais quebras custa mais alertas falsos.</p></div>
                </div>
                <div class="bloco-corpo simulador">
                    <div><div class="grafico"><canvas id="g-dist" role="img"></canvas></div></div>
                    <div class="simulador-controle">
                        <label for="a-limiar">Alertar a partir de <output id="a-limiar-valor"></output></label>
                        <input type="range" id="a-limiar" min="2" max="90" step="1">
                        <div class="medidas" aria-live="polite">
                            <div><span>Quebras avisadas</span><b id="s-recall"></b></div>
                            <div><span>Alertas confirmados</span><b id="s-precisao"></b></div>
                            <div><span>Lavouras alertadas</span><b id="s-alertadas"></b></div>
                        </div>
                        <div class="desfechos">
                            <div class="bom"><span>Quebras avisadas</span><b id="s-vp"></b></div>
                            <div class="ruim"><span>Quebras sem aviso</span><b id="s-fn"></b></div>
                            <div><span>Alertas falsos</span><b id="s-fp"></b></div>
                            <div><span>Normais, sem alerta</span><b id="s-vn"></b></div>
                        </div>
                        <button class="botao pequeno" id="a-limiar-modelo" type="button"></button>
                    </div>
                </div>
            </section>
        </div>`;

    ligarSegmentado(raiz, 'cultura', (v) => { cultura = v; if (v) definirFiltros({ cultura: v }); carregar(); });
    ligarSegmentado(raiz, 'medida', (v) => { medidaHist = v; graficoHistorico(); });
    raiz.querySelector('#a-uf').addEventListener('change', (e) => { definirFiltros({ uf: e.target.value, mun: null }); carregar(); });
    raiz.querySelector('#a-limpar').addEventListener('click', () => { filtrarUf(''); });
    raiz.querySelector('#a-metrica').addEventListener('change', (e) => { metricaUf = e.target.value; graficoUf(); });
    raiz.querySelector('#a-limiar').addEventListener('input', (e) => { limiar = Number(e.target.value) / 100; simular(); });
    raiz.querySelector('#a-limiar-modelo').addEventListener('click', () => { limiar = null; simular(); });

    padroesChart();
    await carregar();
}

export function desmontar() {
    Object.values(graficos).forEach((g) => g.destroy());
    graficos = {}; dados = null;
}

function filtrarUf(uf) {
    definirFiltros({ uf, mun: null });
    raiz.querySelector('#a-uf').value = uf;
    carregar();
}

function padroesChart() {
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.font.size = 13;
    Chart.defaults.color = cor('--tinta-2');
    Chart.defaults.borderColor = cor('--linha');
    Chart.defaults.animation.duration = matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 350;
    Chart.defaults.plugins.legend.position = 'bottom';
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.tooltip.backgroundColor = '#10241a';
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.displayColors = false;
    Chart.defaults.maintainAspectRatio = false;
}

const eixoPct = (max) => ({ beginAtZero: true, max, ticks: { callback: (v) => `${v}%` }, border: { display: false } });
const eixoCat = { grid: { display: false } };

function grafico(id, config, descricao) {
    graficos[id]?.destroy();
    const tela = raiz.querySelector(`#${id}`);
    tela.setAttribute('aria-label', descricao);
    graficos[id] = new Chart(tela, config);
    return graficos[id];
}

async function carregar() {
    const meu = ++pedido;
    const consulta = new URLSearchParams();
    if (cultura) consulta.set('cultura', cultura);
    if (filtros.uf) consulta.set('uf', filtros.uf);
    try {
        const resposta = await api(`/api/analises?${consulta}`);
        if (meu !== pedido || !raiz.isConnected) return;
        dados = resposta;
    } catch (ex) {
        if (meu === pedido) avisar(ex.message);
        return;
    }
    const chip = raiz.querySelector('#a-limpar');
    chip.hidden = !filtros.uf;
    chip.textContent = filtros.uf ? `Só ${nomeUf(filtros.uf)}` : '';
    chip.setAttribute('aria-label', filtros.uf ? `Remover o filtro de ${nomeUf(filtros.uf)}` : '');
    graficoHistorico();
    graficoTeste();
    graficoChuva();
    graficoUf();
    simular(true);
}

function graficoHistorico() {
    const serie = dados.historico;
    const emTaxa = medidaHist === 'taxa';
    const valores = serie.map((s) => (emTaxa ? s.taxa : s.producao_t / 1000));
    const pior = serie.reduce((a, b) => (b.taxa > a.taxa ? b : a), serie[0]);
    raiz.querySelector('#a-hist-nota').textContent = serie.length
        ? `O pior ano foi ${pior.ano}: ${decimal(pior.taxa, 0)}% das lavouras municipais tiveram quebra. Em destaque, anos com 30% ou mais.`
        : 'Sem dados para este filtro.';
    grafico('g-hist', {
        type: 'bar',
        data: {
            labels: serie.map((s) => s.ano),
            datasets: [{
                data: valores,
                backgroundColor: serie.map((s) => (s.taxa >= 30 ? cor('--alto') : cor('--marca'))),
                borderRadius: 4, maxBarThickness: 34,
            }],
        },
        options: {
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: {
                    title: (i) => `Safra ${i[0].label}`,
                    label: (i) => {
                        const s = serie[i.dataIndex];
                        return [`${decimal(s.taxa, 1)}% das lavouras com quebra (${inteiro(s.quebras)} de ${inteiro(s.safras)})`,
                                `Produção: ${inteiro(s.producao_t / 1000)} mil t`,
                                `Área plantada: ${inteiro(s.area_plantada_ha / 1000)} mil ha`];
                    },
                } },
            },
            scales: {
                x: eixoCat,
                y: emTaxa ? eixoPct() : { beginAtZero: true, border: { display: false }, ticks: { callback: (v) => `${inteiro(v)} mil t` } },
            },
        },
    }, `Gráfico de barras: ${emTaxa ? 'percentual de lavouras com quebra' : 'produção em mil toneladas'} por ano, de 2003 a 2025.`);
}

function graficoTeste() {
    const t = dados.teste_por_ano;
    const pendentes = dados.anos_sem_resultado || [];
    raiz.querySelector('#a-teste-nota').textContent = pendentes.length
        ? `Parte das lavouras, em cada safra. ${pendentes.join(' e ')} ainda não tem resultado oficial: aparece só o alerta.`
        : 'Parte das lavouras, em cada safra';
    grafico('g-teste', {
        type: 'bar',
        data: {
            labels: t.map((x) => x.ano),
            datasets: [
                { label: 'Receberam alerta', data: t.map((x) => (x.safras ? 100 * x.alto / x.safras : 0)), backgroundColor: cor('--atencao'), borderRadius: 4, maxBarThickness: 26 },
                { label: 'Quebraram de fato', data: t.map((x) => (x.conferidas ? 100 * x.quebras_reais / x.conferidas : null)), backgroundColor: cor('--alto'), borderRadius: 4, maxBarThickness: 26 },
            ],
        },
        options: {
            plugins: { tooltip: { displayColors: true, callbacks: {
                title: (i) => `Safra ${i[0].label}`,
                label: (i) => `${i.dataset.label}: ${decimal(i.parsed.y, 0)}%`,
                afterBody: (i) => { const x = t[i[0].dataIndex]; return x.conferidas ? `Quebras avisadas: ${inteiro(x.quebras_avisadas)} de ${inteiro(x.quebras_reais)}` : 'Previsão atual: resultado oficial ainda não divulgado'; },
            } } },
            scales: { x: eixoCat, y: eixoPct() },
        },
    }, 'Gráfico de barras: percentual de lavouras que receberam alerta e que quebraram de fato, por safra de 2020 a 2025.');
}

function graficoChuva() {
    const f = dados.chuva;
    grafico('g-chuva', {
        type: 'bar',
        data: { labels: f.map((x) => x.faixa), datasets: [{ data: f.map((x) => x.taxa), backgroundColor: cor('--marca'), borderRadius: 4, maxBarThickness: 44 }] },
        options: {
            plugins: { legend: { display: false }, tooltip: { callbacks: {
                title: (i) => `Chuva: ${i[0].label} do normal`,
                label: (i) => (f[i.dataIndex].taxa == null ? 'Sem lavouras nesta faixa'
                    : `${decimal(i.parsed.y, 0)}% quebraram (${inteiro(f[i.dataIndex].safras)} lavouras na faixa)`),
            } } },
            scales: { x: eixoCat, y: eixoPct() },
        },
    }, 'Gráfico de barras: percentual de lavouras que quebraram em cada faixa de chuva da estação.');
}

function graficoUf() {
    const metrica = METRICAS_UF.find((m) => m.id === metricaUf);
    const lista = dados.por_uf.filter((u) => u[metricaUf] != null && u.quebras_reais >= (metricaUf === 'taxa_quebra' ? 0 : 20))
        .sort((a, b) => b[metricaUf] - a[metricaUf]);
    grafico('g-uf', {
        type: 'bar',
        data: {
            labels: lista.map((u) => u.nome),
            datasets: [{
                data: lista.map((u) => u[metricaUf] * 100),
                backgroundColor: lista.map((u) => (!filtros.uf || filtros.uf === u.uf ? cor('--marca') : cor('--linha'))),
                borderRadius: 4, maxBarThickness: 22,
            }],
        },
        options: {
            indexAxis: 'y',
            onClick: (_, itens) => { if (itens.length) { const u = lista[itens[0].index]; filtrarUf(filtros.uf === u.uf ? '' : u.uf); } },
            onHover: (e, itens) => { e.native.target.style.cursor = itens.length ? 'pointer' : 'default'; },
            plugins: { legend: { display: false }, tooltip: { callbacks: {
                label: (i) => {
                    const u = lista[i.dataIndex];
                    return [`${metrica.nome}: ${decimal(i.parsed.x, 0)}%`,
                            `${inteiro(u.quebras_reais)} quebras em ${inteiro(u.safras)} lavouras`,
                            `Quebras avisadas: ${pct(u.recall)} · alertas confirmados: ${pct(u.precisao)}`];
                },
            } } },
            scales: { x: eixoPct(), y: { grid: { display: false } } },
        },
    }, `Gráfico de barras horizontais: ${metrica.nome.toLowerCase()} por estado.`);
}

// ------------------------------------------------------------- simulador
const linhaLimiar = {
    id: 'linhaLimiar',
    afterDatasetsDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        const x = scales.x.left + (scales.x.right - scales.x.left) * (chart.options.plugins.linhaLimiar.valor);
        ctx.save();
        ctx.strokeStyle = cor('--tinta'); ctx.lineWidth = 2; ctx.setLineDash([5, 4]);
        ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke();
        ctx.restore();
    },
};

function simular(recriar = false) {
    const valor = limiar ?? dados.limiar_modelo;
    const { quebrou, normal, passo } = dados.distribuicao;
    const corte = Math.round(valor / passo);
    const soma = (lista, de, ate) => lista.slice(de, ate).reduce((a, b) => a + b, 0);
    const vp = soma(quebrou, corte), fn = soma(quebrou, 0, corte), fp = soma(normal, corte), vn = soma(normal, 0, corte);
    const total = vp + fn + fp + vn;

    raiz.querySelector('#a-limiar').value = Math.round(valor * 100);
    raiz.querySelector('#a-limiar-valor').textContent = `${Math.round(valor * 100)}%`;
    raiz.querySelector('#s-recall').textContent = vp + fn ? pct(vp / (vp + fn)) : '—';
    raiz.querySelector('#s-precisao').textContent = vp + fp ? pct(vp / (vp + fp)) : '—';
    raiz.querySelector('#s-alertadas').textContent = total ? pct((vp + fp) / total) : '—';
    raiz.querySelector('#s-vp').textContent = inteiro(vp);
    raiz.querySelector('#s-fn').textContent = inteiro(fn);
    raiz.querySelector('#s-fp').textContent = inteiro(fp);
    raiz.querySelector('#s-vn').textContent = inteiro(vn);
    const botao = raiz.querySelector('#a-limiar-modelo');
    botao.textContent = `Voltar ao limiar do modelo (${Math.round(dados.limiar_modelo * 100)}%)`;
    botao.disabled = limiar == null;

    if (!recriar && graficos['g-dist']) {
        graficos['g-dist'].options.plugins.linhaLimiar.valor = valor;
        graficos['g-dist'].update('none');
        return;
    }
    const rotulos = quebrou.map((_, i) => `${Math.round(i * passo * 100)}%`);
    grafico('g-dist', {
        type: 'bar',
        data: {
            labels: rotulos,
            datasets: [
                { label: 'Safra normal', data: normal, backgroundColor: cor('--baixo'), stack: 'a', barPercentage: 1, categoryPercentage: 0.92 },
                { label: 'Safra quebrou', data: quebrou, backgroundColor: cor('--alto'), stack: 'a', barPercentage: 1, categoryPercentage: 0.92 },
            ],
        },
        plugins: [linhaLimiar],
        options: {
            plugins: {
                linhaLimiar: { valor },
                tooltip: { displayColors: true, callbacks: {
                    title: (i) => `Chance de quebra entre ${i[0].label} e ${Math.round((i[0].dataIndex + 1) * passo * 100)}%`,
                    label: (i) => `${i.dataset.label}: ${inteiro(i.parsed.y)} lavouras`,
                } },
            },
            scales: {
                x: { stacked: true, grid: { display: false }, ticks: { maxTicksLimit: 11, maxRotation: 0 }, title: { display: true, text: 'Probabilidade de quebra (calibrada)' } },
                y: { stacked: true, beginAtZero: true, border: { display: false }, title: { display: true, text: 'Lavouras' } },
            },
        },
    }, 'Histograma das chances de quebra estimadas, separando lavouras que quebraram das que tiveram safra normal, com a linha do limiar de alerta.');
}
