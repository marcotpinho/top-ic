# Plano conjunto: avaliação incremental e paralela

Estado: aprovado pelo principal e pelo REVISOR após discussão adversarial; execução liberada nos escopos abaixo. Baselines e integração pertencem ao principal. Nenhuma alteração em docs nem criação/execução de testes unitários. A fase inicial medida obteve ganho de 2,76x; P representa 61–73% do perfil fonte. As decisões conservadoras abaixo preservam sweep completo e workers=1 padrão.

## Evidência e prioridade

O log histórico parallel_corridors_2 registra 900,065 s, 170,603 s de evaluator_seconds e aproximadamente 722,39 s adicionais dentro de evaluation_seconds; há dois agentes e capacidade P90. Esses contadores são aninhados. Os demais 722 s não eram evidência suficiente para atribuir todo custo ao arquivo.

O novo baseline_42, executado pelo principal, mede 21,869 s para 3000 avaliações, 3 iterações e P44: avaliador 7,0296 s, arquivos 14,373 s, P 14,3419 s, dominância de P 13,3446 s, merge 0,5617 s, bookkeeping 0,2136 s, F 0,001516 s, preparação 0,00457 s, duplicatas 0,00513 s, registros 0,000655 s. Geração fica perto de 0,22 s. Logo a primeira entrega é remover reconstrução de chave nos loops e recomputação quadrática da fronteira de P, antes de avaliar ganho paralelo.

## Entregas obrigatórias e divisão

1. Principal: completar baseline sementes 42 e 7, 3000 avaliações, sem término por tempo; implementar chave física cacheada em src/solution.py e atualização incremental de src/entities/pool.py, com vetores pré-calculados em src/entities/selection.py quando necessário. Preservar chaves, ordenação, igualdade de vetores, idades, descartes, truncamento e RNG. Medir as mesmas sementes antes de avançar.
2. AUTOR: src/evaluation_core/evaluator.py e communication.py, mais novo módulo incremental.py se necessário. Reutilizar rotas inteiras inalteradas, conectores e contatos de pares inalterados; manter sweep completo. Expor evaluate(solution, parent=None) com caminho completo quando parent ausente/incompatível. Não modificar Runner/CLI nesta tarefa.
3. REVISOR: novo src/entities/parallel_evaluation.py; separar preparação/integração em archive_updates.py e integrar lotes em search_loop.py/runner.py. ProcessPoolExecutor persistente opcional; workers=1 mantém execução serial. Coordenar com principal qualquer edição de configuração/CLI/profiling.
4. Principal: integrar flags, contadores e ensaios comparativos; AUTOR e REVISOR revisam mutuamente as interfaces e divergências encontradas. Nenhuma etapa especulativa abaixo é requisito desta rodada.

## Contrato incremental

Evaluator.evaluate(solution, parent=None) retorna Solution avaliada e mantém cache_hits/cache_misses. O parente é a base efetiva da passagem, não runner.active_base, que pode ser uma base anterior à perturbação. Reparo pode alterar mais de uma rota: comparar a candidata final reparada com o parente, nunca presumir agente único.

O avaliador não recebe Runner, RNG, F/P ou seen. Uma Solution parente válida já contém Evaluation: trajetórias, visit_times, reached_tasks e communication. Reutilizar trajetória e visit_times somente quando a rota inteira corresponde ao parente. Igualdade física pode ignorar occurrence IDs; comparar todos os campos usados na dinâmica e recompensa. Para rotas alteradas manter cálculo completo de timing/trajectory nesta primeira entrega, reutilizando connect já cacheado por estados/limites. Isso é incremento exato por rota e conector, sem introduzir árvore de segmentos nem aritmética de diferenças que mude arredondamentos.

Crédito e first_visitors são recalculados globalmente: antecipar uma rota muda o primeiro visitante mesmo sem mudar recompensa. Orçamentos continuam verificados antes da comunicação.

Comunicação recebe opcionalmente parent_communication e reusable_agents, junto com parent_horizon. Reutilizar ContactRecord de (m,n) apenas se ambas trajetórias são inalteradas E horizonte coincide exatamente E parâmetros do avaliador são os mesmos. Recalcular integralmente pares incidentes a rotas alteradas; se horizonte mudou, recalcular todos os pares. Não deslocar contatos antigos de um sufixo antecipado. Executar sweep completo com records na ordem original, preservando history, clocks, pair_peaks, integrated_excess e bottleneck. Com dois agentes quase nunca haverá par reutilizável após uma alteração; registrar isso, sem prometer ganho inexistente.

Parente incompatível, ausente ou inválido leva ao avaliador completo. Não esconder exceções de programação com fallback amplo. Contatos numericamente não resolvidos continuam com o status atual.

## Contrato paralelo e ordenação

O pool vive por execução do Runner, inicializa Problem/Config uma vez por processo e encerra em finally/gerenciador de contexto. Workers não recebem Runner. Interface proposta: evaluate_batch(prepared: list[PreparedCandidate], parent: Solution | None) -> Iterator[ScoredCandidate], com índices locais monotônicos, resultado e metadados de cache/tempos. PreparedCandidate inclui candidata final após repair e identificação da família; registro e contadores permanecem no coordenador.

Coordenador gera candidatos na ordem atual, prepara, verifica seen e repara sequencialmente; workers só avaliam candidatas finais. Resultados são incorporados estritamente pela ordem de entrada, nunca por conclusão. Integração atualiza F/P e escolhe base somente após o lote/passagem. Reservar orçamento de avaliações antes de submeter; tratar hits de cache no coordenador para não alterar limite de misses. Não incrementar contadores oficiais de avaliações por trabalhos especulativos descartados. Registrar esses trabalhos separadamente.

Lotes pequenos e limitados, no máximo 2*workers pendências, evitam serialização da população inteira. Snapshot do mesmo parente pode ser enviado uma vez por lote; não enviar cadeias de ancestralidade. Memória limitada pelo número de pendências e caches limitados, não por todas as avaliações já feitas. Caches por processo são independentes; registrar misses físicos separadamente dos misses lógicos usados no orçamento de busca. Nenhum worker usa RNG; geração e desempates mantêm RNG no principal. workers=1 não cria subprocesso.

A equivalência de trajetória de busca é exigida com orçamento de avaliações e sem timeout. Com limite de tempo, cancelamento de futures ainda não iniciados e descarte de resultados posteriores ao deadline são registrados; não prometer trajetória idêntica, nem deadline rígido para trabalhos já em andamento. Exceções de worker sobem ao principal; falha de infraestrutura permite abortar com diagnóstico, não mascarar resultados.

## Contadores e avaliação oráculo

Preservar nomes antigos e explicar inclusão: evaluation_seconds engloba preparo/reparo/integração; evaluator_seconds no paralelo deve representar espera/parede do coordenador, nunca soma de CPU dos workers. Acrescentar separadamente worker_evaluator_seconds (soma), dispatch_seconds, wait_seconds, oracle_seconds, rotas/pares reused e rebuilt, fallbacks, submissions, discarded/cancelled, serialização se mensurável. Cronometrar schedule/build/reward/contacts/sweep dentro do avaliador se isso não exigir estado compartilhado; transmitir deltas de cada job. Não somar tempo de worker ao wall-clock total.

Oráculo opcional executa caminho completo sobre as mesmas candidatas finais, antes de integração, sem consumir RNG nem orçamento da busca. Usar avaliador/cache separado e jamais satisfazer consulta do oráculo com cache incremental. Comparar valid/status/reason, objetivos, tempos, recompensa, primeiros visitantes, trajetórias, contatos, pico, CV, clocks, picos por par, excesso, histórico e gargalo. Índices/IDs/status e decisões de dominância/viabilidade devem coincidir exatamente; numéricos usam tolerância declarada e diferença máxima registrada. Não aceitar diferença de decisão apenas porque floats estão próximos. Em divergência, registrar ocorrência e usar resultado completo como fallback; qualquer divergência não explicada reprova ativação padrão.

Experimentos pelo principal exclusivamente via scripts/run_experiment.py, cada diretório results contendo reprodução, log, run info, JSON, neighborhood log, plots, animação e README derivado de docs/templates/README.md. Comparar para sementes 42 e 7: baseline; chave/P; incremental serial com oráculo; incremental paralelo com workers=2 e oráculo; medições sem oráculo para velocidade. Comparar sequência de candidatas/decisões, contagens, F/P finais e RNG sob 3000 avaliações, parâmetros idênticos e tempo suficiente. Sem testes unitários.

Aceitar correção apenas sem divergências não explicadas e preservando decisões/ordem/contagens. Ganho é medido por wall-clock sem oráculo; se paralelo não ganhar nas duas sementes, manter opcional workers=1 padrão e relatar overhead, sem vender aceleração. Relatar RSS do principal e filhos quando disponível, cache entries e máximo de pendências; reprovar crescimento por retenção de ancestrais ou pendências ilimitadas. Não impor redução arbitrária de tempo como requisito de correção.

## Fora desta rodada

Não implementar checkpoints/clocks incrementais globais, árvore persistente de rotas, vetorização de geração nem fastpath de dois agentes. Lacunas sem contato podem fornecer CV para dois agentes sincronizados e troca instantânea, mas reproduzir diagnósticos completos precisa estudo adicional. Sweep completo reduz risco e permite validar primeiro as fronteiras de cache e paralelismo.

## Debate adversarial e decisões

- REVISOR: evaluator170/900 limita ganho ideal isolado a cerca de 1,234x; prioridade confirmada pelo baseline novo: P e chave primeiro.
- REVISOR: P incremental não pode truncar cada candidato de um batch antes de eliminar dominados globalmente; preservar semântica de update e contadores. Decisão: principal mantém elegibilidade, merge, dominância, truncamento e ordem equivalentes à implementação atual.
- REVISOR: horizonte alterado invalida até pares com agentes intactos; clocks iguais não preservam máximos anteriores. Decisão: exigir horizonte idêntico para reutilização de par e manter sweep completo.
- REVISOR: reservar misses, manter RNG/seen/reparo/arquivos sequenciais. Decisão: contrato acima; equivalência sob orçamento por avaliações, não por tempo.
- Fechamento: principal aprovou o plano e liberou os escopos. AUTOR implementa avaliação incremental; REVISOR integra lote paralelo; revisão cruzada posterior não bloqueia a entrega. Seed7 fase inicial medida: 39,369 → 9,519 s (4,14x), dominância 28,905 → 0,162 s, sem divergências de F, contadores ou histórico, conforme execução do principal.

## Contrato entregue pelo AUTOR

API evaluate(solution, parent=None), controlada por config.incremental_evaluation e verify_incremental. Evaluation.evaluation_context guarda compatibilidade entre instância, alcance, Tc e tolerância de budget. A base é transportável para outro processo sem depender de estar no cache local. Rotas alteradas reconstruídas diretamente, acumulando os mesmos conectores na mesma ordem; rotas intactas reutilizam trajetória e horários. Pares intactos exigem horizonte exatamente igual e sweep continua completo.

O oráculo chama _safe_evaluate(solution) sem parent e sem consultar cache de Evaluation; comparação exata de todos campos de Evaluation (portanto mais estrita que tolerância). Em divergência o resultado completo substitui o incremental antes de cache/integração. Logs limitados aos primeiros 20 casos em evaluator.incremental_divergences, contendo key e fields; total permanece no contador. Conectores e contatos usam seus caches funcionais existentes, limitados a 50000 e 10000 entradas. Cache de Evaluation limitado a 512 entradas FIFO por avaliador, não retém ponteiros de ancestralidade.

evaluator.incremental_metrics é Counter cumulativo: incremental_evaluations, routes_reused, routes_rebuilt, pairs_reused, pairs_rebuilt, fallbacks, oracle_evaluations, oracle_divergences, evaluation_cache_evictions; incremental_seconds e oracle_seconds são durações disjuntas. FallBack inclui ausência/incompatibilidade do parent e divergência. Coordenador deve exportar métricas seriais e deltas de workers separadamente de cache_hits/cache_misses; não somar tempo do oráculo ao custo incremental.

Parecer oficial do REVISOR comunicado pelo principal: ordem, orçamento, caches e contatos foram refutados e resolvidos; contrato aprovado. Experimentos e integração continuam exclusivamente com principal/revisor.

## Revisão adversarial AUTOR da fase 1 contra 1456138

Parecer: aprovado para o fluxo atual, por inspeção estática de solution.py, pool.py e selection.py; sem executar testes. A evidência experimental das sementes 42/7 pertence ao principal.

- Ordem: eligible mantém incumbentes antes das novas entradas; remoções preservam a ordem relativa, e novas entradas sobreviventes são anexadas na ordem original. Truncamento por crowding só acontece ao final do lote, com o mesmo desempate repr(key). Dominadores removidos por candidatos posteriores não precisam ser restaurados: dominância estrita é transitiva.
- Vetores iguais: vector_dominates exige melhoria estrita; soluções com chaves distintas e vetor igual permanecem, como antes. Merge continua deduplicando por chave física antes da dominância.
- Idades e displaced de F: membros existentes conservam o mesmo PoolMember e sua idade; exclusão por front e idade precede dominância. Múltiplos displaced entram na ordem recebida e participam conjuntamente antes do truncamento. Contadores derivam das mesmas cardinalidades finais.
- Chave e pickle: _key é calculada após normalizar rotas, preserva o conteúdo físico anterior e não participa de igualdade/hash da dataclass. replace recalcula a chave; pickle entre processos da mesma versão transporta _key no estado da instância, sem depender de __post_init__ no destino.
- Riscos concretos de compatibilidade: pickle criado antes da inclusão de _key não terá esse atributo ao ser carregado e acessar key falhará; não foi encontrado fluxo atual de persistência pickle no repositório. O novo nondominated difere do anterior se receber duas soluções de mesma chave física com avaliações divergentes: antes o dicionário usava o último vetor para ambas, agora cada ocorrência conserva seu vetor. O contrato de avaliação determinística por chave e o merge de P excluem esse caso no fluxo atual.
- Pré-condição explícita: a otimização assume membros de P já mutuamente não dominados e avaliações imutáveis, propriedade mantida por update e set_expansion_result. Mutação externa de members/avaliações ou carga de um pool não normalizado não é saneada pelo novo update, ao contrário da recomputação antiga. Nenhuma dessas operações foi encontrada no fluxo revisado; não é bloqueador desta entrega.
