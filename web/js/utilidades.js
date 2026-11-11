// Utilidades: gerador de avisos, calculadora de perda, calendário das chuvas, exportação e glossário.
import {
    MESES, api, buscaMunicipio, decimal, definirFiltros, esc, filtros, htmlAviso, inteiro, ligarCopiar,
    ligarSegmentado, nomeCultura, opcoes, opcoesAnos, opcoesSelect, pct, reais, segmentado, selo,
} from './nucleo.js';

const SACA_KG = 60;
const limites = () => opcoes.limiares[filtros.ano] || Object.values(opcoes.limiares)[0];
const glossario = () => [
    ['Quebra de safra', 'A lavoura do município rendeu menos da metade do que costuma render. O “habitual” é a média dos cinco anos anteriores, para a mesma cultura.'],
    ['Risco alto, atenção e risco baixo', `Risco alto: a chance de quebra passou do limite em que o serviço emite alerta, ${pct(limites().alto)} na safra de ${filtros.ano}. Atenção: entre ${pct(limites().atencao)} e esse limite. Risco baixo: abaixo de ${pct(limites().atencao)}. O limite parece baixo porque a quebra é rara: na média, cerca de 16% das lavouras quebraram entre 2020 e 2025.`],
    ['Chance de quebra', 'A probabilidade estimada para aquele município, cultura e safra. Ela foi calibrada: de cada dez lavouras com chance de 40%, cerca de três quebraram no teste. A estimativa ainda puxa um pouco para cima, e não é uma certeza.'],
    ['Chuva da estação (% do normal)', 'Quanto choveu nos quatro meses mais chuvosos do lugar, comparado com a média dos anos anteriores. 100% é um ano normal; 60% é um ano seco.'],
    ['Quebras avisadas e alertas confirmados', 'Quebras avisadas: de todas as perdas que aconteceram, quantas receberam alerta. Alertas confirmados: de todos os alertas emitidos, quantos viraram perda de fato.'],
    ['Resultado real', 'O que o IBGE registrou depois da colheita, na Produção Agrícola Municipal. Serve para conferir se o alerta acertou.'],
    ['Garantia-Safra', 'Benefício federal para agricultores familiares do Semiárido que perdem pelo menos metade da produção por seca ou excesso de chuva. Regras e prazos devem ser confirmados na prefeitura ou no sindicato.'],
];
let raiz, municipio = null, pedido = 0;

export async function montar(conteudo) {
    raiz = conteudo;
    raiz.innerHTML = `
        <div class="pagina-topo">
            <div>
                <h1>Utilidades</h1>
                <p>Ferramentas para o dia a dia do técnico: preparar o aviso, estimar o tamanho da perda, ver quando chove em cada lugar e levar os dados para uma planilha.</p>
            </div>
        </div>

        <form class="filtros" onsubmit="return false">
            <label class="campo cresce">Município
                <span class="busca"><input type="search" id="u-busca" placeholder="Digite o nome" autocomplete="off"></span>
            </label>
            <div class="campo">Cultura${segmentado('cultura', opcoes.culturas, filtros.cultura)}</div>
            <label class="campo">Safra<select id="u-ano">${opcoesSelect(opcoesAnos(), filtros.ano)}</select></label>
        </form>

        <div class="utilidades-grade">
            <section class="painel-bloco">
                <div class="bloco-topo"><div><h2>Aviso ao agricultor</h2><p class="nota">O texto que o serviço enviaria, pronto para copiar</p></div><span id="u-selo"></span></div>
                <div class="bloco-corpo" id="u-aviso" style="display:grid;gap:.9rem"></div>
            </section>

            <div style="display:grid;gap:1.25rem">
                <section class="painel-bloco">
                    <div class="bloco-topo"><div><h2>Calculadora de perda</h2><p class="nota">Quanto uma quebra representa para uma lavoura deste município</p></div></div>
                    <div class="bloco-corpo">
                        <div class="duas-colunas">
                            <label class="campo">Área plantada (hectares)<input type="number" id="u-area" min="0.1" step="0.5" value="3" inputmode="decimal"></label>
                            <label class="campo">Preço da saca de 60 kg (R$)<input type="number" id="u-preco" min="0" step="1" value="" placeholder="opcional" inputmode="decimal"></label>
                        </div>
                        <div class="resultado" id="u-calculo" aria-live="polite"></div>
                    </div>
                </section>

                <section class="painel-bloco">
                    <div class="bloco-topo"><div><h2>Calendário das chuvas</h2><p class="nota" id="u-cal-nota"></p></div></div>
                    <div class="bloco-corpo"><div class="calendario" id="u-calendario"></div></div>
                </section>
            </div>

            <section class="painel-bloco">
                <div class="bloco-topo"><div><h2>Levar os dados para a planilha</h2><p class="nota">Lista de municípios com nível, chance de quebra, chuva e resultado real, em CSV (abre no Excel)</p></div></div>
                <div class="bloco-corpo">
                    <div class="duas-colunas">
                        <label class="campo">Safra<select id="e-ano">${opcoesSelect(opcoesAnos(), filtros.ano)}</select></label>
                        <label class="campo">Cultura<select id="e-cultura">${opcoesSelect(opcoes.culturas, filtros.cultura)}</select></label>
                    </div>
                    <label class="campo" style="margin-top:.75rem">Estado<select id="e-uf">${opcoesSelect(opcoes.ufs, filtros.uf, 'Todo o Semiárido')}</select></label>
                    <a class="botao primario" id="e-baixar" download style="margin-top:1rem">Baixar CSV</a>
                </div>
            </section>

            <section class="painel-bloco">
                <div class="bloco-topo"><h2>O que significa cada termo</h2></div>
                <div class="bloco-corpo glossario">
                    ${glossario().map(([termo, texto]) => `<details><summary>${esc(termo)}</summary><p>${esc(texto)}</p></details>`).join('')}
                </div>
            </section>
        </div>`;

    buscaMunicipio(raiz.querySelector('#u-busca'), (m) => { definirFiltros({ mun: m.cod_mun }); carregar(); });
    ligarSegmentado(raiz, 'cultura', (v) => { definirFiltros({ cultura: v }); carregar(); });
    raiz.querySelector('#u-ano').addEventListener('change', (e) => { definirFiltros({ ano: e.target.value }); carregar(); });
    raiz.querySelector('#u-area').addEventListener('input', calcular);
    raiz.querySelector('#u-preco').addEventListener('input', calcular);
    ['e-ano', 'e-cultura', 'e-uf'].forEach((id) => raiz.querySelector(`#${id}`).addEventListener('change', linkExportar));
    linkExportar();

    if (!filtros.mun) {
        // sem município escolhido, começa pelo de maior risco da safra
        const r = await api(`/api/risco?ano=${filtros.ano}&cultura=${filtros.cultura}${filtros.uf ? '&uf=' + filtros.uf : ''}`);
        if (r.municipios[0]) definirFiltros({ mun: r.municipios[0].cod_mun });
    }
    await carregar();
}

export function desmontar() { municipio = null; }

function linkExportar() {
    const consulta = new URLSearchParams({ ano: raiz.querySelector('#e-ano').value, cultura: raiz.querySelector('#e-cultura').value });
    const uf = raiz.querySelector('#e-uf').value;
    if (uf) consulta.set('uf', uf);
    raiz.querySelector('#e-baixar').href = `/api/exportar.csv?${consulta}`;
}

async function carregar() {
    const meu = ++pedido;
    const aviso = raiz.querySelector('#u-aviso');
    if (!filtros.mun) { semMunicipio('Escolha um município no campo acima.'); return; }
    try {
        const d = await api(`/api/municipio/${filtros.mun}?ano=${filtros.ano}&cultura=${filtros.cultura}`);
        if (meu !== pedido || !raiz.isConnected) return;
        municipio = d;
    } catch (ex) {
        if (meu === pedido) semMunicipio(`${ex.message} Tente a outra cultura ou outra safra.`);
        return;
    }
    const d = municipio;
    raiz.querySelector('#u-busca').value = `${d.municipio} (${d.uf})`;
    raiz.querySelector('#u-selo').innerHTML = selo(d.nivel);
    aviso.innerHTML = htmlAviso(d.mensagens);
    ligarCopiar(aviso, d.mensagens);
    calcular();
    calendario();
}

function semMunicipio(texto) {
    municipio = null;
    raiz.querySelector('#u-selo').innerHTML = '';
    raiz.querySelector('#u-aviso').innerHTML = `<p class="vazio">${esc(texto)}</p>`;
    raiz.querySelector('#u-calculo').innerHTML = '<p class="nota">Escolha um município para calcular.</p>';
    raiz.querySelector('#u-calendario').innerHTML = '';
    raiz.querySelector('#u-cal-nota').textContent = '';
}

function calcular() {
    const caixa = raiz.querySelector('#u-calculo');
    if (!municipio) return;
    const d = municipio;
    const area = Number(raiz.querySelector('#u-area').value);
    const preco = Number(raiz.querySelector('#u-preco').value);
    if (!d.rend_habitual) {
        caixa.innerHTML = `<p class="nota">Não há rendimento recente de ${esc(nomeCultura(d.cultura).toLowerCase())} registrado para ${esc(d.municipio)}.</p>`;
        return;
    }
    if (!(area > 0)) { caixa.innerHTML = '<p class="nota">Informe a área plantada, em hectares.</p>'; return; }
    const esperado = area * d.rend_habitual;         // kg num ano habitual
    const perda = esperado / 2;                       // numa quebra, perde-se pelo menos metade
    const sacas = (kg) => kg / SACA_KG;
    caixa.innerHTML = `
        <div><span class="nota">Numa quebra, a perda é de pelo menos</span>
            <div class="grande">${decimal(sacas(perda), 0)} sacas</div>
            <span class="nota">${inteiro(perda)} kg de ${esc(nomeCultura(d.cultura).toLowerCase())}${preco > 0 ? `, ou cerca de <b>${reais(sacas(perda) * preco)}</b>` : ''}</span></div>
        <dl>
            <dt>Rendimento habitual em ${esc(d.municipio)}</dt><dd>${inteiro(d.rend_habitual)} kg/ha</dd>
            <dt>Colheita esperada em ${decimal(area, 1)} ha</dt><dd>${decimal(sacas(esperado), 0)} sacas</dd>
            <dt>Chance de quebra na safra ${d.ano}</dt><dd>${Math.round(d.prob * 100)}%</dd>
        </dl>
        <p class="nota pequeno">Rendimento habitual: média municipal das cinco últimas safras (IBGE). A lavoura de cada família pode render mais ou menos que a média.</p>`;
}

function calendario() {
    const d = municipio;
    const chuva = d.chuva_normal || [];
    const max = Math.max(...chuva, 1);
    const inicio = d.mes_inicio_chuvas;                       // 1 a 12
    const estacao = [0, 1, 2, 3].map((k) => (inicio - 1 + k) % 12);
    const mesAlerta = estacao[3];
    raiz.querySelector('#u-cal-nota').textContent =
        `Em ${d.municipio}, chove mais de ${d.estacao[0]} a ${d.estacao[3]}. O alerta mais confiável sai no fim de ${d.estacao[3]}.`;
    raiz.querySelector('#u-calendario').innerHTML = MESES.map((mes, i) => {
        const classe = i === mesAlerta ? 'chuvoso alerta-mes' : (estacao.includes(i) ? 'chuvoso' : '');
        const dica = `${mes}: ${inteiro(chuva[i])} mm em média${i === mesAlerta ? ' (mês do alerta)' : ''}`;
        return `<div class="${classe}" title="${dica}"><i style="height:${Math.max(3, (chuva[i] / max) * 100)}%"></i>${mes}</div>`;
    }).join('');
    raiz.querySelector('#u-calendario').setAttribute('aria-label',
        `Chuva média por mês em ${d.municipio}: ${MESES.map((m, i) => `${m} ${inteiro(chuva[i])} mm`).join(', ')}`);
    raiz.querySelector('#u-calendario').setAttribute('role', 'img');
}
