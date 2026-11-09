# Parecer adversarial: paralelização e reutilização da avaliação

Parecer: plano 08 aprovado para implementação no escopo mínimo, condicionado à validação experimental pelo principal. Não implica ganho demonstrado nem equivalência já verificada. Nenhum experimento ou teste unitário foi executado pelo revisor.

## Evidência e refutações

- O log `results/2026-11-08/parallel_corridors_2/run.log` mede 900,065 s totais e 170,603 s de avaliador. O ganho ideal isolado seria apenas 1,234x; IPC, serialização e caches frios podem eliminar esse ganho. Não somar contadores aninhados.
- O baseline informado pelo principal em `results/2026-11-08/parallel_incremental/baseline_42` mede 21,869 s/3000 avaliações, com 13,3446 s em dominância de P e 7,0296 s no avaliador. A prioridade é chave física cacheada e dominância incremental. Em `src/entities/selection.py:nondominated`, a implementação original reconstruía chaves durante comparações quadráticas; `src/entities/pool.py:update` refazia a fronteira a cada proposta.
- Dominância incremental deve preservar igualdade de vetores, ordem, idades, contadores e truncamento. Candidatos de uma mesma chamada update não podem ser truncados intermediariamente: até um candidato posteriormente truncado pode dominar outro. Arquivos continuam atualizados por candidata, na ordem original.
- `src/entities/runner.py:exhausted` consulta avaliações exatas e tempo; preparar/reparar um lote sem reservar misses permite exceder o orçamento. Reservas anteriores entram no limite de admissão, sem antecipar contadores oficiais de avaliações. `archive_updates.py:_is_duplicate` deve verificar também a candidata reparada antes da submissão. Seen e reparos permanecem no coordenador; sob timeout seus efeitos antecipados podem permanecer e não se promete trajetória idêntica.
- `archive_updates.py:_record_acceptance` registra o número de avaliações no momento da incorporação. Não incrementar antecipadamente evaluated/exact_evaluations nem incorporar por ordem de conclusão. Inicialização é serial; nenhum worker acessa RNG, F/P ou Runner.
- `evaluation_core/contacts.py:pair_contacts` depende de trajetórias e horizonte. Mudança de duração desloca o sufixo e pode alterar todos os contatos incidentes. Mudança do horizonte invalida inclusive pares intactos. Não deslocar intervalos antigos para representar novos encontros.
- `evaluation_core/communication.py:sweep` acumula pair_peaks, integrated_excess, history e bottleneck além dos clocks. Clocks coincidentes não autorizam copiar CV final. Nesta rodada o sweep permanece completo; sem checkpoints nem especialização de dois agentes.

## Interface e condições de aceitação

`Runner.evaluate_batch(candidates, family, parent)` é exclusivo do VND. O parente é a base efetiva da passagem. Workers chamam `Evaluator.evaluate(solution, parent=None)` e retornam solução, tempo, deltas de incremental_metrics e divergências limitadas. Preparação, reparo, deduplicação, reservas e incorporação são sequenciais no coordenador. Cache lógico fica no coordenador; hits/misses físicos dos workers são diagnósticos separados. workers=1 não cria subprocessos. Spawn é lazy, pool persistente, pendências limitadas a min(batch_size,2*workers), shutdown anterior à montagem do resultado.

Resultados são incorporados por ordem de entrada. Com orçamento por avaliações e tempo suficiente devem coincidir contagens, escolhas, RNG e F/P; com timeout aceita-se prefixo diferente, com trabalho descartado/cancelado registrado. Falhas de worker propagam: não transformá-las silenciosamente em solução inválida. Tempo somado de workers não é tempo de parede.

Principal valida as sementes e os mesmos parâmetros: baseline, chave/P, incremental serial com oráculo, paralelo com oráculo, e desempenho sem oráculo. Aceitação exige zero divergências não explicadas e comparação da sequência/decisões, não apenas da fronteira final. Não se exige nem se promete aceleração antes das medições; workers=1 continua padrão. Experimentos e artefatos pertencem ao principal e seguem AGENTS.md.

## Escopo mínimo aprovado

Reutilizar rotas inteiras intactas e contatos de pares intactos apenas com horizonte/contexto idênticos; recalcular crédito e sweep completo. Paralelizar somente avaliações finais de candidatos VND após reparo. Não vetorizar geração, criar grafos persistentes, checkpoints ou reordenar o método. Otimizações de P/chaves e CLI/profiling pertencem ao principal; avaliador incremental pertence ao autor; integração de lotes pertence ao revisor.
