# Relatório atualizado — Auditoria dos dados e dashboard de enchentes

**Atualizado em:** 27/11/2026  
**Projeto:** análise de inundação em Porto Alegre e Taquara  
**Arquivo JSON usado pelo dashboard:** `dados/inct_simulacao.json`  
**Aplicação:** `main.py`

## 1. Objetivo

Documentar a estrutura e as limitações do JSON do INCT SiMAI, registrar como as fontes externas entram no projeto e descrever os indicadores e mapas da dashboard. A pergunta principal da análise viária é: **qual extensão de vias aparece dentro da mancha de inundação mapeada?**

Essa métrica representa sobreposição espacial. Não significa que as vias tenham sido oficialmente interditadas ou que toda a sua extensão tenha ficado alagada.

## 2. Dados e coleta

### JSON do INCT SiMAI

O arquivo está organizado por nível do Guaíba e bairro. A auditoria anterior encontrou 71 níveis, de 3,0 m a 10,0 m em passos de 0,1 m, e 94 bairros por nível, totalizando 6.674 combinações bairro/nível. O arquivo contém contagens estimadas de prédios e população, além de campos derivados de porcentagem e população afetada.

### Fontes externas previstas no coletor

O script `coleta_bases.py` coleta ou tenta coletar:

- **Zenodo:** GeoPackage de cheias da Região Hidrográfica do Guaíba e metadados/glossário, conforme os arquivos listados no registro.
- **Atlas Digital:** CSV de registros de desastres, com tentativa de filtragem para Porto Alegre e Taquara.
- **SMAMUS:** camada ArcGIS de cotas de inundação de 3,0 m a 5,35 m, salva em GeoJSON.

O script também grava `coleta_info.json` com data e links das fontes. Uma falha de uma fonte é informada no terminal; portanto, a mensagem de conclusão da rotina não prova que todas as fontes foram coletadas. A pasta `dados/originais/` estava vazia na última inspeção deste relatório. As chamadas externas e os arquivos brutos precisam ser executados/obtidos antes de uma validação espacial reproduzível.

### Fontes usadas pelo cálculo viário do dashboard

O dashboard usa um GeoPackage do Zenodo para a mancha de água e a malha viária do GeoPackage do Zenodo. Se não encontrar vias no arquivo, consulta o OpenStreetMap via OSMnx. Também consulta o OpenStreetMap para obter o limite municipal. Essas etapas requerem acesso à internet quando os dados não estão em cache/localmente disponíveis.

O CSV do Atlas e o GeoJSON da SMAMUS são coletados pelo script, mas **não alimentam os indicadores atuais de quilômetros de vias**. A camada de inundação usada é selecionada pelo nome entre as camadas disponíveis; a camada efetivamente usada aparece na dashboard.

## 3. Auditoria e tratamento do JSON

### Verificações registradas na auditoria anterior

A auditoria anterior informou:

- nenhum valor negativo nos campos avaliados;
- nenhum registro com prédios afetados acima do total;
- nenhum total de prédios igual a zero;
- nenhuma chave bairro/nível duplicada;
- nenhum total de prédios ou população-base variando indevidamente entre níveis;
- 12 quedas na quantidade de prédios afetados, em cinco bairros.

As quedas foram mantidas, pois as contagens disponíveis não permitem inferir o valor correto. Elas ocorrem em Arquipélago, Centro Histórico, Espírito Santo, Lageado e Rubem Berta. Os detalhes por nível e contagem estão no relatório de auditoria anterior fornecido pela equipe.

### Inconsistência pendente entre a auditoria e o arquivo que a aplicação lê

A auditoria anterior registra que, em Boa Vista do Sul nos níveis 7,2 m e 7,3 m, os campos derivados deveriam ser ajustados de `percentage = 29` para `28` e de `affected_population = 784` para `757`. Porém, o arquivo presente em `dados/inct_simulacao.json` ainda contém os valores originais `29` e `784` nesses dois níveis.

O leitor atual do dashboard converte o JSON aninhado para uma tabela e só recalcula a porcentagem quando o campo está ausente ou zerado; ele não aplica essas duas correções conhecidas. Portanto, **a aplicação ainda não está consumindo a versão corrigida descrita na auditoria anterior**. Antes de apresentar esses dois registros como limpos, é necessário substituir o arquivo por uma versão limpa validada ou aplicar as correções no processamento, registrando essa decisão. A convenção `ceil` usada para inferir os campos derivados foi observada na auditoria, mas não deve ser atribuída oficialmente ao INCT sem confirmação.

### Inconsistências não monotônicas

Em cenários cumulativos, espera-se que a quantidade de prédios afetados não diminua quando o nível sobe. A auditoria anterior identificou 12 quedas em cinco bairros. O dashboard mantém os valores fornecidos pelo arquivo e exibe um aviso; não interpola nem corrige as contagens automaticamente. O relatório completo deve manter os níveis e valores de cada queda para permitir conferência e devolutiva ao INCT.

## 4. Como a dashboard funciona

### Tela 1 — Porto Alegre

- Controle deslizante de 3,0 m a 10,0 m em passos de 0,1 m.
- Indicadores de população estimada, prédios afetados e bairros com prédios atingidos.
- Gráfico da porcentagem de prédios afetados para os bairros atingidos na cota selecionada.
- Curva da população estimada ao longo dos níveis, com a referência de 5,35 m e o nível escolhido.
- Ranking de bairros ordenado pela porcentagem de prédios afetados. A tabela também mostra contagens e população estimadas.
- Coluna “Margem de erro” indicando que a fonte não informa um intervalo de confiança ou margem numérica.
- Mapa de vias com filtro por tipo e limite municipal destacado.

O ranking usa a porcentagem como critério principal. Assim, um bairro menor pode aparecer acima de outro com mais prédios afetados em números absolutos. A ordem não representa severidade por número total de pessoas.

### Tela 2 — Taquara

- Indicadores de quilômetros de vias cobertos pela mancha, percentual da rede analisada dentro da mancha e extensão total mapeada.
- Mapa de trechos atingidos, filtro por tipo de via e gráficos de distribuição e extensão por grupo.
- Limite municipal destacado, incluindo as áreas rurais representadas pelo polígono municipal obtido no OpenStreetMap.

Porto Alegre também possui o mapa de vias com filtro por tipo. Nos dois municípios, o filtro atualiza os indicadores e visualizações viárias.

## 5. Agrupamento dos tipos de via

Para facilitar a leitura por pessoas que não trabalham com mapas, as categorias da base são agrupadas em:

1. **Rodovias e vias principais:** rodovias, vias expressas, vias arteriais principais e acessos correspondentes.
2. **Vias secundárias e coletoras:** vias secundárias, coletoras e acessos correspondentes.
3. **Ruas locais e residenciais:** vias residenciais e ruas locais sem classificação mais específica.
4. **Vias de serviço e acessos:** acessos a estacionamentos, áreas de serviço e usos semelhantes.

Ciclovias, caminhos de pedestres, trilhas e caminhos, estradas rurais, escadarias e outras vias permanecem separados. Os grupos são uma simplificação baseada nos atributos da fonte; exemplos como RS-020, Freeway ou avenidas urbanas ajudam a explicar a ideia, mas não substituem a classificação nem a conferência do trecho individual.

## 6. Método dos quilômetros

1. Obtém-se o polígono do município e recortam-se a mancha de água e as vias por esse limite.
2. As geometrias são projetadas em SIRGAS 2000 / UTM zona 22S (EPSG:31982), para calcular comprimento em metros.
3. Para cada linha viária, calcula-se a parte que cruza o polígono de inundação.
4. O comprimento dessa interseção é convertido para quilômetros e somado.
5. O percentual é calculado como quilômetros sobrepostos à mancha divididos pela extensão total de vias no recorte municipal.

O mapa desenha **somente os trechos com sobreposição**. O total da malha e a porcentagem continuam considerando todos os trechos viários do município, inclusive os que ficam fora da mancha. A rosca “dentro/fora” apresenta essa comparação para dar contexto aos indicadores.

## 7. Limitações e interpretação responsável

- Os valores do INCT são estimativas de simulação, não previsões nem contagens oficiais de campo.
- A população afetada presume distribuição uniforme entre prédios residenciais e não residenciais; não equivale a pessoas observadas no local.
- O JSON não fornece margem de erro ou intervalo de confiança. Por isso, a dashboard informa que a margem não foi disponibilizada; não se apresenta uma porcentagem inventada.
- As quedas não monotônicas e as duas correções derivadas pendentes precisam ser resolvidas/documentadas antes de afirmar que o JSON usado no painel é a versão limpa final.
- Os quilômetros são uma medida geométrica sobre a mancha selecionada. Não confirmam interdição, condição do pavimento, profundidade, duração da água ou operabilidade da via.
- O valor depende da versão e cobertura espacial do GeoPackage, da camada de água selecionada, da malha do OpenStreetMap e do limite municipal usado.
- Se não houver polígono de inundação sobre Taquara, o dashboard avisa que a área não tem cobertura e não estima um número.
- A coleta automática do Atlas pode ser bloqueada pelo site. O sucesso ou falha precisa ser conferido por fonte no terminal e pelos arquivos gravados.
- A comparação com a mancha observada do Zenodo é apenas contextual enquanto não houver sobreposição com bairros e edificações e uma validação temporal/espacial equivalente ao JSON do INCT.

## 8. Fontes e links

- INCT SiMAI / Plataforma Flood: <https://inct-simai.com.br/?page=home>
- Zenodo, registro usado na coleta: <https://zenodo.org/records/12593168>
- Zenodo, versão mais recente citada na auditoria anterior: <https://zenodo.org/records/14617475>
- Atlas Digital, página de downloads: <https://atlasdigital.mdr.gov.br/paginas/downloads.xhtml>
- SMAMUS, camada de cotas de inundação: <https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/01_PUBLICACOES/cotas_inundacao_300_535/FeatureServer/0>
- OpenStreetMap: <https://www.openstreetmap.org/>
- Mapa da Prefeitura citado na auditoria anterior: <https://prefeitura.poa.br/sites/default/files/usu_doc/hotsites/smpae/observapoa/MapaInundacaoPOA_06052024-1-2.pdf>

As datas de coleta do GeoPackage e das outras fontes devem ser lidas de `dados/originais/coleta_info.json`, gerado quando o coletor é executado. O arquivo do JSON do INCT é datado localmente; essa data não indica quando os dados foram originalmente produzidos.

## 9. Uso de inteligência artificial

Ferramentas de IA foram usadas como apoio à implementação e revisão da dashboard, organização deste relatório e explicação de conceitos. A equipe deve revisar os resultados, confirmar as correções e estar preparada para explicar o código, as fontes e as limitações. Esta declaração deve ser mantida e ajustada para descrever exatamente a participação da equipe.

## 10. Pendências antes de apresentar resultados como finais

1. Corrigir a divergência entre o JSON lido pelo dashboard e as duas correções descritas na auditoria.
2. Executar o coletor e registrar data, arquivos obtidos e falhas por fonte.
3. Confirmar se a camada de inundação selecionada cobre Porto Alegre e Taquara e conferir os metadados/data da camada.
4. Validar a classificação dos trechos e, se possível, conferir os quilômetros calculados com uma amostra no mapa.
5. Publicar o repositório e o dashboard e completar a entrega em PDF conforme as instruções do curso; essa publicação não está feita por este relatório.
