# Execução do plano de avaliação incremental e paralela

## Estado inicial e autoria

- Worktree anterior registrada e enviada a origin/main em `1456138`.
- Plano: `08-parallel-incremental-plan.md`, escrito pelo agente AUTOR (Gibbs) e submetido a refutação do agente REVISOR (Noether).
- Principal: integração, otimização de chaves/P, configuração/CLI/profiling e experimentos.
- Nenhum teste unitário foi criado ou executado. Todos os ensaios usam `scripts/run_experiment.py`, com artefatos e README baseado no template sob `results/2026-11-08/parallel_incremental/`.

## Diagnóstico medido

Os baselines foram encerrados por 3000 avaliações, não por tempo. Parâmetros comuns: mapa parallel_corridors, R=6, Tc=4, passos 2/0.5, tau=0.001, no máximo 5 passagens, raio FREE=6 e limite de tempo 180 s.

| Semente | Baseline (s) | Chaves/P (s) | Ganho | Dominância P antes/depois (s) |
|---|---:|---:|---:|---:|
| 42 | 21.8690 | 7.9374 | 2.76x | 13.3446 / 0.1054 |
| 7 | 39.3693 | 9.5186 | 4.14x | 28.9053 / 0.1622 |

A fronteira F serializada e os campos generated, evaluated, exact_evaluations, valid, invalid, duplicate, accepted, accepted_pool, iterations, selection_history, initialization_history e objective_history coincidem exatamente nos pares baseline/chaves-P.

A versão inicial não exportava os membros de P, portanto essa comparação não comprova identidade dos seus membros individualmente. Para as próximas fases, foi adicionado fingerprint SHA-256 da sequência (chave física, vetor 3D, idade) e os vetores de P aos diagnósticos. O fingerprint preserva ordem e idade, relevantes para a seleção.

## Artefatos iniciais

- `results/2026-11-08/parallel_incremental/baseline_42/`
- `results/2026-11-08/parallel_incremental/baseline_7/`
- `results/2026-11-08/parallel_incremental/pool_optimized_42/`
- `results/2026-11-08/parallel_incremental/pool_optimized_7/`
- Comparação reproduzível dos JSON salvos: `.venv/bin/python results/2026-11-08/parallel_incremental/pool_optimized_42/compare.py`.

## Integração e avaliação restante

A preencher com os ensaios de avaliação incremental serial, paralelo, oráculo e três agentes heterogêneos assim que a implementação conjunta terminar. A propagação temporal completa continua como caminho de referência; checkpoints globais e a especialização em lacunas de dois agentes não fazem parte desta entrega.
