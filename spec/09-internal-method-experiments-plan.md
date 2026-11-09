# Plano experimental interno do método TOP-ICC

## 1. Objetivo e escopo

Este plano avalia o método TOP-ICC sem compará-lo com algoritmos externos. A campanha deve responder seis perguntas:

1. O método converge de forma estável quando recebe mais avaliações e mais tempo?
2. Quais componentes causam ganho mensurável de qualidade ou viabilidade?
3. O comportamento permanece estável quando alcance, recorrência e hiperparâmetros mudam?
4. Como custo e memória crescem com tarefas, agentes e processos de avaliação?
5. A avaliação incremental e paralela preserva os resultados lógicos da execução serial completa?
6. Os mecanismos alegados no artigo aparecem nos resultados: uso do pool, reparo de comunicação, FREE/relay, diversidade de rotas e contribuição das vizinhanças?

O plano não inclui TOP-CC, solvers exatos, heurísticas externas ou qualquer outro baseline externo. As únicas comparações são entre configurações do próprio método.

## 2. Princípios da campanha

- Congelar um commit antes da campanha principal. Resultados com mudanças locais não entram no artigo.
- Usar orçamento de avaliações exatas como eixo primário. Tempo de parede é um resultado, não o orçamento principal de qualidade.
- Executar campanhas de qualidade sem concorrência entre experimentos. Cada execução pode usar dois workers, mas duas execuções não devem disputar CPU ao mesmo tempo.
- Usar as mesmas sementes em configurações pareadas.
- Não escolher a melhor semente para figuras. A solução ilustrativa será da semente cuja hipervolume final estiver mais próxima da mediana da configuração.
- Não modificar hiperparâmetros após observar os resultados principais. Pilotos são identificados e excluídos da análise final.
- Executar toda busca por `scripts/run_experiment.py`, de modo que cada pasta terminal contenha `reproduce.sh`, `run.log`, `run-info.json`, `result.json`, log de vizinhanças, métricas, plots, animação e README baseado no template do repositório.
- Registrar falhas e timeouts; não substituir silenciosamente uma execução.

## 3. Instâncias

### 3.1 Conjunto principal

As quatro instâncias principais usam os mapas com orçamento de voo triplicado, pois permitem separação e reencontro sem tornar o orçamento físico o único gargalo.

| Código | Arquivo | Agentes | Tarefas | $R$ | $T_c$ |
|---|---|---:|---:|---:|---:|
| `post_disaster` | `maps/scenarios/triple_budget_20261012/01_post_disaster.json` | 3 | 64 | 12 | 12 |
| `wildfire` | `maps/scenarios/triple_budget_20261012/02_wildfire_front.json` | 3 | 55 | 14 | 15 |
| `pipeline` | `maps/scenarios/triple_budget_20261012/03_pipeline_corridor.json` | 3 | 48 | 15 | 20 |
| `agriculture` | `maps/scenarios/triple_budget_20261012/05_agriculture.json` | 3 | 180 | 18 | 25 |

### 3.2 Probes de mecanismo

| Código | Arquivo | Finalidade | $R$ | $T_c$ |
|---|---|---|---:|---:|
| `parallel_corridors` | `maps/probes/parallel_corridors/instance.json` | divisão de tarefas e reencontros | 6 | 4 |
| `free_waypoint_relay` | `maps/probes/free_waypoint_relay/instance.json` | utilidade de FREE/relay | 14 | 12 |
| `ten_rewards_origin` | `maps/probes/ten_rewards_origin/instance.json` | caso pequeno e denso | 5 | 8 |
| `ten_rewards_far_relay` | `maps/probes/ten_rewards_far_relay/instance.json` | comunicação em excursão distante | 4 | 13 |

Os valores da tabela são os valores efetivamente usados pela nova campanha. Eles substituem recomendações históricas com handshake; o modelo atual usa comunicação instantânea enquanto os agentes estão em alcance.

## 4. Sementes e configuração de referência

Sementes principais, definidas antes da execução:

```text
7, 19, 31, 42, 53, 67, 79, 97, 109, 127
```

Experimentos reduzidos usam as cinco primeiras. Validações caras com oráculo usam `7` e `42`.

Configuração de referência:

```text
evaluation_workers       = 2
evaluation_batch_size    = 8
incremental_evaluation   = true
verify_incremental       = false
max_iterations           = 1000000
initialization_fraction  = 0.20
neighborhood_hv_tau      = 0.001
neighborhood_max_passes  = 5
archive_size             = 100
dominated_archive_size   = 100
eps_reward               = 1.0
eps_time                 = 0.1
headings                 = 8
speed_fractions          = 0.1, 0.25, 0.5, 0.75, 1.0
velocity_segment_lengths = 2, 3
neighborhood_candidates  = 120
communication_repair     = 3 rounds
selection_policy         = nd_count
```

O orçamento principal de avaliações, $E^*$, é definido por um piloto reproduzível:

1. executar uma vez cada instância principal com semente 42, 1000 avaliações e limite de 1800 s;
2. calcular a menor taxa observada $r_{\min}$ em avaliações exatas por segundo;
3. definir
   
   ```text
   E* = max(5000, min(20000, 1000 * floor(0.8 * 1800 * r_min / 1000)))
   ```
4. se alguma execução principal não atingir $E^*$ em 3600 s, descartar toda a rodada iniciada e reduzir $E^*$ para o maior múltiplo de 1000 atingido por todas as quatro instâncias. A decisão e os pilotos permanecem salvos.

O teto temporal das execuções por avaliações é 3600 s. Uma execução principal que parar por tempo, iterações ou erro não é tratada como se tivesse completado o orçamento.

## 5. Instrumentação obrigatória antes da campanha

### 5.1 Histórico de progresso

Adicionar `statistics.progress_history` ao resultado. Registrar uma linha no início, a cada 50 novas avaliações exatas e no final, com:

- `elapsed_seconds` desde o início da busca;
- `exact_evaluations`;
- `iterations`;
- `front_size` e `pool_size`;
- `hypervolume` normalizada com referência fixa $(1,1)$;
- `maximum_reward` em $\mathcal F$;
- menor tempo médio entre soluções de recompensa máxima;
- `minimum_pool_cv`;
- primeira avaliação e primeiro tempo em que $\mathcal F$ ficou não vazio;
- contagens cumulativas de entradas em $\mathcal F$, entradas em $\mathcal P$ e reparos que reduziram $CV$.

O registro não deve alterar RNG, seleção ou arquivos. A hipervolume deve usar a escala fixa já usada pelo solver: recompensa total da instância e maior orçamento de voo.

### 5.2 Motivo de término e identidade lógica

Adicionar ao resultado:

- `termination_reason`: `evaluation_limit`, `time_limit`, `iteration_limit`, `empty_search`, `error` ou `completed`;
- fingerprint ordenado de $\mathcal F$ e de $\mathcal P$;
- fingerprint cumulativo da sequência de candidatos preparados e integrados;
- estado final ou hash estável do RNG;
- pico de RSS do coordenador;
- máximo de jobs pendentes e pico de cache dos workers, já disponíveis parcialmente.

Esses campos permitem distinguir equivalência lógica de mera igualdade do front final.

### 5.3 Flags necessárias para ablação

Expor no CLI, sem mudar os defaults:

- `--communication-repair-rounds N`;
- `--initialization-mode full|direct_only`;
- `--disable-ruin-recreate`;
- `--pool-max-age N`;
- `--recreate-sample-slots N` e `--recreate-noise-scale X`, usados apenas na análise suplementar.

As vizinhanças já podem ser removidas com `--disable`. O modo `direct_only` deve avaliar somente a rota START--END antes da busca; todas as inserções posteriores continuam disponíveis.

### 5.4 Manifesto e launcher

Criar `scripts/run_paper_method_campaign.py` com subcomandos `materialize`, `run`, `resume` e `status`. O launcher deve:

1. ler um manifesto JSON sem inferir parâmetros ausentes;
2. recusar árvore Git suja na campanha principal;
3. materializar a lista completa de execuções antes de iniciar;
4. chamar `scripts/run_experiment.py` para cada execução;
5. executar uma busca de cada vez;
6. não sobrescrever uma pasta existente;
7. permitir `resume` apenas para execuções ausentes ou explicitamente marcadas como falha;
8. salvar stdout/stderr do launcher e os códigos de saída;
9. atualizar `campaign-status.json` atomicamente após cada execução.

## 6. Organização em `/results`

Usar a data real de início:

```text
results/YYYY-MM-DD/paper_method_internal/
├── README.md
├── campaign.json
├── campaign-status.json
├── launcher.log
├── pilots/
├── 01_correctness/
├── 02_reference/
├── 03_ablation/
├── 04_communication_sensitivity/
├── 05_hyperparameter_robustness/
├── 06_scaling/
├── 07_evaluation_efficiency/
├── generated_instances/
└── analysis/
```

Cada execução terminal segue:

```text
<experiment>/<instance>/<variant>/seed_XXX/
```

Exemplo:

```text
results/2026-11-09/paper_method_internal/
  03_ablation/wildfire/no_pool/seed_042/
```

O `--output-dir` sempre aponta para essa pasta terminal. `run_experiment.py` cria o README a partir de `docs/templates/README.md`. O README da raiz da campanha descreve o manifesto, o commit, o comando do launcher e o estado final. A pasta `analysis/` também possui README com o comando exato do parser e a lista de arquivos produzidos.

Nenhum resultado antigo é misturado com a nova campanha. Resultados antigos podem ser citados como motivação, mas não entram nas tabelas ou testes estatísticos.

## 7. Execução base

Exemplo de execução de referência, onde `<E_STAR>` é o orçamento congelado pelo piloto:

```sh
.venv/bin/python scripts/run_experiment.py \
  --output-dir results/YYYY-MM-DD/paper_method_internal/02_reference/wildfire/full/seed_042 \
  -- \
  --instance maps/scenarios/triple_budget_20261012/02_wildfire_front.json \
  --seed 42 \
  --evaluation-workers 2 \
  --evaluation-batch-size 8 \
  --max-seconds 3600 \
  --max-evaluations <E_STAR> \
  --max-iterations 1000000 \
  --initialization-budget-fraction 0.2 \
  --neighborhood-hv-tau 0.001 \
  --neighborhood-max-passes 5 \
  --archive-size 100 \
  --dominated-archive-size 100 \
  --eps-reward 1 \
  --eps-time 0.1 \
  --headings 8 \
  --speed-fractions 0.1 0.25 0.5 0.75 1 \
  --velocity-segment-lengths 2 3 \
  --neighborhood-candidates 120 \
  --communication-repair-rounds 3 \
  --comm-range 14 \
  --recurrence-bound 15
```

O launcher gera esse comando a partir do manifesto; o comando é mostrado para definir exatamente a execução esperada.

## 8. Experimentos

### E0. Piloto de orçamento

**Pergunta.** Qual orçamento comum cabe no limite de tempo sem transformar tempo em critério de parada?

**Matriz.** Quatro instâncias principais, semente 42, configuração completa, 1000 avaliações.

**Saída.** Taxa de avaliações, tempo por componente e $E^*$ congelado. Os quatro pilotos ficam em `pilots/` e não entram nas medidas de qualidade.

### E1. Correção incremental, paralela e reprodutibilidade

**Pergunta.** A otimização de avaliação preserva cada decisão observável?

**Matriz.** Quatro probes, sementes 7 e 42, 1000 avaliações, máximo de 3600 s:

1. avaliação completa serial: `--disable-incremental-evaluation --evaluation-workers 1`;
2. incremental serial com oráculo: `--verify-incremental --evaluation-workers 1`;
3. incremental paralela com oráculo: `--verify-incremental --evaluation-workers 2`;
4. repetição da configuração 3 em uma pasta distinta.

**Critérios de aprovação.** Zero divergência do oráculo; mesmas sequências de candidatos integrados, contagens, histórico de seleção, fingerprints de $\mathcal F$ e $\mathcal P$ e estado final do RNG; repetição byte-equivalente nos campos lógicos. Tempos, RSS e campos de profiling podem diferir.

Qualquer divergência bloqueia E2--E7 até ser explicada ou corrigida.

### E2. Convergência e robustez entre sementes

**Pergunta.** Quanto o método melhora com avaliações e tempo, e qual é sua dispersão estocástica?

**Matriz.** Quatro instâncias principais, dez sementes, configuração de referência, $E^*$ avaliações.

**Curvas primárias.** Mediana e intervalo interquartil de hipervolume versus avaliações exatas. Usar grade `0,50,...,E*` e carregamento do último valor observado.

**Curvas secundárias.** Hipervolume versus tempo em `0,1,2,5,10,20,30,60,120,300,600,1200,1800,3600` s; recompensa máxima viável; menor $CV$ do pool; tamanho de $\mathcal F$; probabilidade empírica de já ter encontrado solução viável.

**Resumos finais.** Hipervolume, recompensa máxima, menor tempo na recompensa máxima, tamanho do front, tempo e avaliações até a primeira solução viável, AUC da hipervolume por avaliações, fração de bases vindas do pool e Jaccard médio entre tarefas das rotas.

**Critério de saturação.** Declarar convergência prática apenas quando a mediana do ganho de hipervolume no último 20% das avaliações for menor que 1% da hipervolume final. Caso contrário, escrever “melhora ainda ativa no orçamento observado”.

### E3. Ablação dos componentes do método

**Pergunta.** Quais componentes são necessários para qualidade, viabilidade ou velocidade de convergência?

**Instâncias.** `wildfire`, `agriculture`, `parallel_corridors` e `free_waypoint_relay`.

**Sementes.** As dez sementes principais.

**Orçamento.** 5000 avaliações exatas e 3600 s. A configuração `full` pode reutilizar o checkpoint de 5000 avaliações de E2; nenhuma nova execução é necessária quando o prefixo lógico for idêntico.

**Variantes pareadas.** Uma alteração por vez:

| Variante | Alteração |
|---|---|
| `full` | método completo |
| `no_pool` | `--disable-pool-selection` |
| `no_comm_repair` | `--communication-repair-rounds 0` |
| `no_comm_neighborhoods` | `--disable relay free_near_visit free_segment unlink` |
| `direct_initialization` | `--initialization-mode direct_only` |
| `no_ruin_recreate` | `--disable-ruin-recreate` |

**Métricas.** Hipervolume e AUC por avaliações são primárias. Recompensa máxima, sucesso de viabilidade, avaliações até primeira viável, tamanho do front, menor $CV$ e diversidade de rotas são secundárias.

**Análise.** Comparar cada ablação com `full` pela mesma semente e instância. Reportar mediana da diferença absoluta, diferença relativa, intervalo bootstrap pareado de 95% e teste de Wilcoxon pareado. Aplicar correção de Holm dentro de cada métrica primária. Não usar apenas $p$-valor: efeito e intervalo são obrigatórios.

### E4. Sensibilidade à dificuldade de comunicação

**Pergunta.** Como a busca responde a restrições de comunicação mais fáceis ou difíceis?

**Instâncias.** Quatro instâncias principais.

**Sementes.** Cinco sementes reduzidas.

**Orçamento.** 5000 avaliações, 3600 s, configuração completa.

**Variação de $T_c$.** Fixar $R$ e multiplicar $T_c$ por `0.5, 0.75, 1.0, 1.5, 2.0`.

**Variação de $R$.** Fixar $T_c$ e multiplicar $R$ por `0.75, 1.0, 1.25`.

O ponto base é executado uma vez e reutilizado nas duas séries. Cada valor de $T_c$ é uma otimização independente; não filtrar retrospectivamente um front obtido para outro $T_c$.

**Métricas.** Taxa de sucesso viável, hipervolume, recompensa máxima, avaliações até primeira viável, menor $CV$ e proporção de bases do pool.

**Apresentação.** Heatmaps por instância e curvas normalizadas pelo ponto base. Não fazer teste de hipótese para monotonicidade da heurística; relatar tendência e dispersão.

### E5. Robustez a hiperparâmetros

**Pergunta.** As conclusões dependem de uma escolha estreita de hiperparâmetros?

**Instâncias.** `wildfire` e `agriculture`.

**Sementes.** Cinco sementes reduzidas.

**Orçamento.** 3000 avaliações, 3600 s.

**Desenho.** Uma variável por vez; o nível central é a referência e é reutilizado:

| Parâmetro | Níveis |
|---|---|
| capacidade de $\mathcal P$ | 50, 100, 200 |
| candidatos por vizinhança | 60, 120, 240 |
| máximo de passes | 1, 3, 5 |
| fração de inicialização | 0.10, 0.20, 0.30 |
| headings | 4, 8, 16 |
| escala conjunta de epsilon | 0.5, 1.0, 2.0 vezes `(1,0.1)` |
| limiar de hipervolume $\tau$ | 0, 0.001, 0.01 |

**Métricas.** Hipervolume, AUC, recompensa, tempo por avaliação, memória e número de passes. O objetivo é mostrar robustez e custo, não escolher novamente o melhor nível. Se um nível extremo for claramente inválido ou instável, ele permanece reportado.

### E6. Escalabilidade em tarefas e agentes

**Pergunta.** Como custo, memória e qualidade normalizada crescem com o tamanho do problema?

Antes de executar, criar `scripts/generate_scaling_instances.py`. O gerador deve ser determinístico, registrar sua versão e salvar as instâncias produzidas em `generated_instances/`, que faz parte do bundle de resultados.

**Escala de tarefas.** Partir de `05_agriculture.json`, manter três agentes e selecionar `N=20,40,80,160` tarefas por amostragem farthest-point determinística, preservando posições e recompensas originais.

**Escala de agentes.** Partir de `03_pipeline_corridor.json`, manter todas as tarefas e criar `M=2,3,4,6` agentes idênticos copiando limites, orçamento e velocidade inicial do agente de referência. Início e destino permanecem iguais.

**Sementes.** Cinco sementes reduzidas. **Orçamento.** 3000 avaliações e 3600 s.

**Métricas de custo.** Segundos por 1000 avaliações, tempo do avaliador, tempo de contatos/sweep quando instrumentado, tempo de arquivo/pool, pico de RSS, número de intervalos de contato, tamanho dos caches e máximo de pendências.

**Métricas de qualidade.** Hipervolume normalizada, recompensa como fração da recompensa total, taxa de viabilidade e tamanho do front. Qualidade não deve ser comparada em valores absolutos entre instâncias de tamanhos diferentes.

**Análise.** Gráficos log-lineares e ajuste descritivo de inclinação; não declarar complexidade empírica assintótica com apenas quatro tamanhos.

### E7. Eficiência da avaliação incremental e paralela

**Pergunta.** Quanto tempo é economizado sem alterar a trajetória lógica?

**Instâncias.** `parallel_corridors`, `wildfire` e `agriculture`.

**Sementes.** Cinco sementes reduzidas. **Orçamento.** 3000 avaliações e 3600 s.

**Incremental.** Comparar, com um worker:

- avaliação completa: `--disable-incremental-evaluation`;
- incremental sem oráculo;
- incremental com oráculo, reportada apenas como custo de validação.

**Workers.** Com incremental e sem oráculo, usar `w=1,2,3,4,6,8`, batch 8. Como o batch limita pendências, resultados acima de quatro workers medem também a saturação esperada.

**Batch.** Com dois workers, usar batch `2,4,8,16`.

**Métricas.** Wall-clock, speedup, eficiência paralela, avaliações/s, RSS do coordenador e workers, dispatch, espera, soma de CPU dos workers, reutilização de rotas/pares, cache e serialização se disponível.

**Critério de equivalência.** Todos os fingerprints e contadores lógicos devem coincidir com o serial completo. Se não coincidirem, os tempos não são publicados como aceleração equivalente.

### E8. Análise de mecanismos sem novas execuções

Usar E2 e E3 para responder:

- quais vizinhanças geram, avaliam e inserem soluções em $\mathcal F$ e $\mathcal P$;
- com que frequência reparo reduz $CV$ ou chega a zero;
- quantas bases vêm de $\mathcal P$ e quantas chegam depois a $\mathcal F$;
- frequência e posição de FREE visits nas soluções finais;
- diversidade de conjuntos de tarefas entre agentes e entre soluções do front;
- distribuição do tempo entre geração, avaliação, comunicação, arquivo e pool;
- diferenças entre inicialização cooperativa, partição e construção incremental.

Não interpretar contagens brutas sem denominador. Para cada operador, reportar taxas por candidato avaliado e por chamada.

## 9. Parsing e validação dos bundles

Criar `scripts/analyze_paper_method_campaign.py`. Comando:

```sh
.venv/bin/python scripts/analyze_paper_method_campaign.py \
  --campaign-dir results/YYYY-MM-DD/paper_method_internal
```

O parser deve primeiro validar:

- toda entrada do manifesto possui pasta terminal;
- `result.json`, `run-info.json`, `metrics.json`, `run.log`, `reproduce.sh` e README existem;
- SHA-256 da instância corresponde ao manifesto;
- commit, Python e dependências são homogêneos;
- parâmetros salvos correspondem exatamente à variante;
- status é bem-sucedido e o motivo de término é o esperado;
- orçamento de avaliações foi alcançado quando exigido;
- não há `NaN` ou infinito;
- oráculos não apresentam divergência;
- fingerprints coincidem onde equivalência é exigida.

Se uma validação falhar, escrever `analysis/validation-errors.json` e terminar com status diferente de zero sem gerar tabelas finais.

### 9.1 Arquivos tabulares

Produzir:

- `runs.csv`: uma linha por execução, configuração e métricas finais;
- `progress.csv`: uma linha por checkpoint;
- `operators.csv`: uma linha por execução e família;
- `initialization.csv`: uma linha por proposta de inicialização;
- `repairs.csv`: uma linha por chamada de reparo;
- `parallel.csv`: contadores incrementais e paralelos;
- `front.csv`: uma linha por solução final de $\mathcal F$;
- `statistics.json`: efeitos, intervalos, testes e correções;
- `validation-report.json`: completude e equivalência.

Campos comuns: experimento, instância, variante, semente, commit, hash da instância, orçamento, motivo de término, workers e batch.

### 9.2 Regras de reconstrução

- Curvas por avaliações usam carregamento do último checkpoint observado.
- Curvas por tempo usam o último checkpoint com timestamp menor ou igual ao ponto da grade.
- AUC é calculada pela regra do trapézio e dividida pelo comprimento do eixo, ficando na mesma escala da métrica.
- Recompensa e tempo são extraídos apenas de soluções com `CV=0`.
- A solução “best reward” maximiza recompensa e desempata por menor tempo médio.
- A solução “knee” minimiza distância euclidiana ao ponto ideal após normalização fixa da instância.
- A semente representativa minimiza a distância absoluta entre sua hipervolume e a mediana; empates usam a menor semente.
- Execuções incompletas não recebem imputação e aparecem em uma tabela de falhas.

### 9.3 Estatística

- Reportar mediana, IQR, média e desvio padrão por transparência, usando mediana/IQR como resumo principal.
- Usar bootstrap pareado por semente, 10.000 reamostragens, para intervalo de 95% das diferenças.
- Usar Wilcoxon pareado nas ablações, com Holm por família de métricas.
- Reportar também probabilidade pareada de superioridade e diferença relativa mediana.
- Não agregar instâncias com escalas diferentes antes de normalizar por instância.
- Não tratar as dez sementes como substituto para diversidade de instâncias.

## 10. Figuras e tabelas geradas

Salvar em `analysis/figures/` e `analysis/tables/`:

### Figuras principais

1. `convergence-evaluations.pdf`: hipervolume mediana e IQR por avaliações, painel por instância.
2. `convergence-time.pdf`: mesma medida por tempo.
3. `ablation-effects.pdf`: diferenças pareadas e IC 95% para hipervolume/AUC.
4. `communication-sensitivity.pdf`: heatmaps de viabilidade, recompensa e hipervolume.
5. `scaling-cost.pdf`: tempo, RSS e avaliações/s por tarefas e agentes.
6. `mechanism-flow.pdf`: bases de $\mathcal F/\mathcal P$, reparos e conversões para o front.
7. `representative-paths.pdf`: soluções da semente mediana, selecionadas por regra prévia.

### Tabelas principais

1. instâncias e configuração congelada;
2. resultados finais da configuração completa por instância;
3. ablações com efeito pareado e intervalo;
4. correção e eficiência incremental/paralela;

### Material suplementar

- robustez de hiperparâmetros;
- detalhes de operadores;
- todos os fronts finais;
- tabela de falhas/timeouts;
- fingerprints e validações de equivalência;
- comandos e manifestos completos.

Gerar PDF e PNG dos gráficos. CSV e JSON são as fontes; valores não devem ser transcritos manualmente para tabelas.

## 11. Integração no artigo

Substituir integralmente os experimentos históricos de `paper/experiments.tex`, pois eles usam handshake e semântica de arquivo anteriores ao modelo atual.

Estrutura proposta para a seção experimental:

1. **Experimental setup:** instâncias, hardware, commit, orçamento por avaliações, sementes e hiperparâmetros.
2. **Correctness and reproducibility:** oráculo, fingerprints e determinismo serial/paralelo.
3. **Anytime convergence and robustness:** curvas por avaliações e tempo; dispersão entre sementes.
4. **Ablation study:** efeito dos cinco componentes removidos.
5. **Communication difficulty:** alcance, recorrência e probabilidade de viabilidade.
6. **Scalability and computational cost:** tarefas, agentes, incremental e workers.
7. **Mechanism analysis:** pool, reparo, operadores e FREE visits.
8. **Limitations and threats to validity:** instâncias sintéticas, dez sementes, ausência de obstáculos/colisões e orçamento finito.

No texto principal:

- usar resultados de E2, E3, E4 e o resumo de E7;
- mover E5, detalhes de E6 e diagnósticos completos de E8 para suplemento quando faltar espaço;
- não afirmar convergência para ótimo; usar “estabilização dentro do orçamento”;
- não afirmar que um componente é necessário quando o intervalo de efeito inclui zero;
- não atribuir causalidade a contagens de operadores isoladas;
- manter separadas qualidade por avaliações e velocidade por tempo;
- indicar explicitamente que os experimentos não comparam o método a trabalhos externos.

Atualizar `paper/README.md` com a nova raiz de resultados e comandos para reconstruir figuras e tabelas. Copiar para `paper/` apenas arquivos finais necessários à compilação, ou referenciá-los por caminho relativo estável; os dados-fonte permanecem em `/results`.

## 12. Ordem de execução e gates

1. Implementar e revisar a instrumentação da Seção 5.
2. Executar E0 e congelar $E^*$ no manifesto.
3. Executar E1. Prosseguir somente com zero divergências.
4. Executar E2 e verificar se todas as instâncias atingem $E^*$.
5. Executar E3, E4 e E8, que formam o núcleo do artigo.
6. Executar E6 e E7 para custo e escalabilidade.
7. Executar E5 para robustez suplementar.
8. Rodar o parser, corrigir apenas problemas de extração e congelar `analysis/`.
9. Atualizar `paper/experiments.tex`, conclusão, resumo e README com valores gerados.

Gate para considerar a campanha encerrada:

- manifesto completo e sem execuções silenciosamente ausentes;
- zero divergências de correção;
- todas as comparações de qualidade terminadas por avaliações;
- todos os bundles reproduzíveis e com README;
- análise gerada automaticamente a partir de JSON/CSV;
- artigo sem valores provenientes da campanha histórica incompatível.

## 13. Estimativa de quantidade de execuções

Sem contar reuso de checkpoints:

| Bloco | Execuções aproximadas |
|---|---:|
| E0 piloto | 4 |
| E1 correção | 32 |
| E2 referência | 40 |
| E3 ablação | até 240 |
| E4 comunicação | 140 |
| E5 hiperparâmetros | 150 |
| E6 escala | 40 |
| E7 eficiência | até 195 |

E3, E5 e E7 são os blocos mais caros. Para uma primeira submissão, a ordem de prioridade é E1, E2, E3, E4, E7, E6 e E5. A redução de custo deve remover blocos inteiros de menor prioridade, sem reduzir sementes depois de observar resultados.
