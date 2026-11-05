# Busca TOP-ICC com arquivo factível e pool de cobertura

## Escopo

Esta é a única versão proposta. O artigo não apresenta comparação A/B entre estruturas de arquivo. Cada valor de $T_c$ exige uma execução independente. Decisões não redefinidas aqui permanecem iguais às do algoritmo atual.

## Avaliação

- Objetivos reportados: maximizar recompensa única $Q$ e minimizar tempo médio de voo $\bar c$; internamente, usar $(-Q,\bar c)$.
- Calcular $CV(S)=\sum_{n\ne m}\max(0,P_{nm}-T_c)$ pela matriz completa dos picos de defasagem dos pares ordenados.
- `CV=0` se e somente se $\Delta\le T_c$. `CV`, $P_{nm}$, $A_c$ e sinais de alcance/handshake são restrições ou diagnósticos, nunca objetivos.
- Uma solução é viável quando estrutura, movimento, orçamento e `CV=0` são satisfeitos. Crédito vem somente de visitas `TASK` explícitas.
- Todos os caminhos do avaliador produzem exatamente dois objetivos. Um cache miss da avaliação completa é uma avaliação exata e a unidade do orçamento.

## Arquivo factível F

- Aceitar apenas soluções viáveis e Pareto não dominadas em $(-Q,\bar c)$.
- Usar caixas epsilon com larguras iniciais `(1 recompensa, 0.1 s)`, um representante por caixa, escolhido pela distância normalizada ao canto.
- Capacidade `N_F=100`. Ao excedê-la, dobrar as duas larguras e refiltrar até caber.
- Enviar para `P` candidatos válidos que não ficam em `F` e membros removidos por dominância ou substituição de caixa.
- Publicar somente `F` como resultado da busca.

## Pool P e cobertura

- Capacidade `N_P=100`. Cada membro guarda solução, `CV`, $Q$, $\bar c$, subregião e idade.
- Normalizar como $(1-Q/Q_{total},\bar c/B_{max})$ com limites fixos da instância.
- Usar os 21 vetores $(i/20,1-i/20)$ e associar pelo menor ângulo.
- Cobertura ignora viabilidade de comunicação. Em rodada `itr`, a subregião $k$ admite até `itr - n_k` membros de `P`, com $n_k$ igual à ocupação de `F`.
- Escolher candidato objetivo-não-dominado de menor Tchebycheff em relação ao ideal de `F`; desempatar por menor `CV`, objetivos e chave estável.
- Repetir rodadas até a capacidade ou esgotamento dos candidatos.
- Uma expansão melhora quando insere em `F` ou produz membro de `P` que domina o pai pela relação com restrição. Zerar a idade nesse caso; incrementar caso contrário. Remover idade maior que cinco mesmo com vagas.
- Registrar descartes por idade, capacidade e transferência para `F` separadamente.

## Seleção de base

- Construir `ND_F` por Pareto em $(-Q,\bar c)$ somente dentro de `F` e `ND_P` por Pareto tridimensional em $(CV,-Q,\bar c)$ somente dentro de `P`.
- Definir $n_F=|ND_F|$, $n_P=|ND_P|$, $\rho_P=n_P/(n_F+n_P)$ e $\rho_F=1-\rho_P$. Se um arquivo estiver vazio, usar o outro.
- Sortear os dois participantes somente no conjunto não dominado do arquivo escolhido.
- Em `ND_F`, vencer pelo maior crowding bidimensional; empates usam chave estável.
- Em `ND_P`, vencer pelo menor `CV`, desempatando por maior $Q$, menor $\bar c$ e chave estável.

## Iteração

1. Selecionar a base.
2. Remover aleatoriamente 10–40% das visitas `TASK` por rota, cadeias regionais ou relação espaço-temporal.
3. Reconstruir com regret-2, priorizando tarefas ausentes e sem duplicar tarefas já visitadas pela equipe; usar ruído pequeno e o único RNG da execução.
4. Se a solução reconstruída for válida e tiver `CV>0`, executar até três rodadas de reparo. Em cada rodada avaliar um lote com até oito links do gargalo, convites com anfitrião parado e `FREE` a `0.9R` em grade 3x3, e retempo de encontros existentes. Prosseguir com menor `CV`, desempatar por maior $Q$, e parar sem redução estrita.
5. Executar o VND atual. Cada candidata distinta recebe avaliação completa e atualiza `F` e `P`.
6. Repetir cada vizinhança enquanto o hipervolume de `F` aumentar mais que tau, até `p_max`, como no algoritmo atual.
7. Parar pelo orçamento de avaliações exatas; tempo de parede é proteção operacional. A inicialização consome no máximo 20% dos dois limites.

## Aleatoriedade e instrumentação

- Criar um único `Random(seed)` por execução e passá-lo a todos os componentes. Não usar aleatoriedade global nem reseeding.
- Por família: geradas, válidas, inválidas por motivo, avaliações exatas, hits, entradas em `F`, entradas em `P` e agentes cujas rotas foram alteradas.
- Por iteração, indexada por avaliações exatas: menor/mediana de `CV` em `P`; tamanhos e subregiões ocupadas de `F`/`P`; cache hit rate; idade média e descartes; fração de bases de `P`; hipervolume, tamanho de `F` e recompensa máxima.
- Registrar $\rho_F$ e $\rho_P$ em cada seleção e registrar individualmente toda semente/proposta de inicialização, sua recompensa declarada/avaliada, `CV`, validade e destino.
- Registrar conversões pool→`F`, distinguindo reparos; chamadas de reparo que reduziram e zeraram `CV`; avaliações por nova entrada em `F`; tempo; e média de Jaccard entre tarefas dos agentes nas soluções de `F`.
- Salvar as métricas em `result.json` e `metrics.json`.

## Documentação e saídas

- Atualizar formulação, variáveis, modelagem, arquitetura, metodologia do artigo, README, ajuda da CLI e template de resultados em conjunto.
- O artigo descreve esta proposta única e não relata o experimento A/B anteriormente planejado.
- Adaptar hipervolume, histórico e gráficos para dois objetivos.
- Todo experimento usa `scripts/run_experiment.py` e salva, na pasta diária em `results/`, reprodução, log, metadados, JSON, métricas, log de vizinhanças, gráficos, animação e README baseado no template.

## Campanha solicitada

Executar em paralelo por 300 s, seed 42 e teto alto de avaliações/iterações:

- `parallel_corridors`: `R=6`, `Tc=4`;
- `ten_rewards_origin`: `R=5`, `Tc=4`;
- `02_wildfire_front`: `R=14`, `Tc=15`;
- `05_agriculture`: `R=18`, `Tc=25`.

## Ablation de seleção da pool

- Comparar a proposta corrigida (`--selection-policy nd_count`) com a política anterior (`--selection-policy legacy_fraction`).
- Usar os mesmos quatro mapas, pelo menos cinco sementes pareadas e exatamente o mesmo limite de avaliações exatas para os dois tratamentos de cada mapa.
- Definir uma referência fixa de hipervolume separadamente para cada mapa. Não comparar valores absolutos de hipervolume entre mapas.
- Reportar mediana e intervalo interquartil por mapa para hipervolume final, curva por avaliações, recompensa máxima, pontos de `F`, fração de bases de `P` e avaliações por entrada em `F`.
- Avaliar reparo pelo número de candidatas reparadas que efetivamente entram em `F`, além das taxas de redução e de zeragem de `CV`.

## Critérios de aceite

- Todo item publicado em `front` tem dois objetivos, respeita movimento/orçamento e possui `CV=0`.
- `P` nunca excede 100; nenhum membro sobrevivente tem idade acima de cinco.
- A mesma semente reproduz decisões estocásticas enquanto o limite de avaliações é o critério ativo.
- Contadores por família fecham com misses/hits globais e os quatro bundles contêm todos os artefatos exigidos.
