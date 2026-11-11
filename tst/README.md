# Roteiro de execução de `spec/plano-testes.md`

Esta pasta implementa o plano como scripts executáveis, sem adicionar casos ao `pytest`. Os grupos C, D, E e G6 executam o otimizador exclusivamente por `scripts/run_experiment.py`; cada célula produz o bundle completo exigido em `results/`. Os grupos A, B, F e G são verificações analíticas e usam `run_verification.py` para também produzir `report.json`, log, reprodução e README derivado de `docs/templates/README.md`.

## Dependências e escopo

Use o Python do ambiente do projeto a partir da raiz:

```sh
.venv/bin/python --version
```

E5 e E7 foram removidos do plano. E2 usa `--communication-repair-rounds 0`, e E6 usa `--disable-ruin-recreate`. `run_campaign.py` grava `blocked.json` vazio para tornar explícito que não há ablações pendentes na matriz atual.

O teste G7 deverá falhar enquanto referências não históricas a handshake permanecerem no repositório. Corrija essa pendência separadamente antes da campanha completa.

## 1. Gerar instâncias derivadas

```sh
.venv/bin/python tst/generate_instances.py
```

Isso cria em `tst/instances/` M1/M2/M3/M5, variações de orçamento, escala e velocidade, além de `bridge2.json` e `bridge3.json`.

## 2. Checks analíticos rápidos

```sh
.venv/bin/python tst/run_verification.py \
  --suite A --output-dir results/plan-tests/$(date +%F)/A-contacts

.venv/bin/python tst/run_verification.py \
  --suite B --output-dir results/plan-tests/$(date +%F)/B-propagation

.venv/bin/python tst/run_verification.py \
  --suite G --output-dir results/plan-tests/$(date +%F)/G-static
```

- A cobre A1–A9: contatos constantes, cruzamentos, tangências, incerteza numérica, quártico, fronteiras de peças, presença terminal e reuso incremental.
- B cobre B1–B9: relay, store-and-forward, ordem temporal, cadeia, componente simultânea, CV e assimetria.
- G cobre monotonicidade de CV, equivalência `Delta <= Tc`, independência dos picos, M=1 no avaliador de comunicação, permutação, handshake e estabilidade de tangências. G6 é completado depois das duas runs determinísticas.

## 3. Conferir a campanha sem executá-la

```sh
.venv/bin/python tst/run_campaign.py \
  --group C --group D --group E --group G6 \
  --output-root results/plan-tests/$(date +%F) \
  --dry-run
```

Revise os comandos impressos e o `ledger.json`. Nenhum otimizador é iniciado com `--dry-run`.

## 4. Piloto

O piloto limita cada célula a 500 avaliações e 60 segundos. Ele valida infraestrutura, não os critérios científicos da spec.

```sh
.venv/bin/python tst/run_campaign.py \
  --group C --seeds 101 \
  --output-root results/plan-tests/$(date +%F)-pilot \
  --pilot
```

Também é possível acrescentar `--batch-eval` para uma campanha explicitamente matricial.

## 5. Campanhas completas

Execute separadamente para facilitar retomadas:

```sh
.venv/bin/python tst/run_campaign.py \
  --group C \
  --maps m2 \
  --output-root results/plan-tests/$(date +%F) \
  --resume

.venv/bin/python tst/run_campaign.py \
  --group C \
  --maps m2 \
  --max-evaluations 1000000 \
  --max-seconds 900 \
  --output-root results/plan-tests/$(date +%F)-million-evals \
  --batch-eval \
  --resume

.venv/bin/python tst/run_campaign.py \
  --group D \
  --output-root results/plan-tests/$(date +%F) \
  --resume

.venv/bin/python tst/run_campaign.py \
  --group E \
  --output-root results/plan-tests/$(date +%F) \
  --resume

.venv/bin/python tst/run_campaign.py \
  --group G6 \
  --output-root results/plan-tests/$(date +%F) \
  --resume
```

Parâmetros padrão conforme a spec:

- C: sementes 101–110, 20.000 avaliações, 2 mapas × 5 valores de Tc × 10 sementes = 100 runs.
- D: sementes 101–110, 5.000 avaliações, todos os níveis de alcance, agentes, orçamento, dispersão, ponte e velocidade.
- E: sementes 201–210, 5.000 avaliações, base e todas as ablações em M2, incluindo E2 sem reparo e E6 sem ruin-and-recreate. Use `--include-m3` para repetir toda a matriz em M3.
- G6: duas runs idênticas com seed 42 e 2.000 avaliações.

Cada comando chama internamente, por célula:

```sh
.venv/bin/python scripts/run_experiment.py --output-dir results/... -- --instance ...
```

`--resume` pula apenas diretórios que já possuam `result.json`.

## 6. Determinismo G6 e avaliador batch F

```sh
.venv/bin/python tst/run_verification.py \
  --suite G \
  --output-dir results/plan-tests/$(date +%F)/G-properties \
  -- \
  --determinism-results \
  results/plan-tests/$(date +%F)/G6/determinism-1/result.json \
  results/plan-tests/$(date +%F)/G6/determinism-2/result.json
```

Para F1–F6, informe uma run com frente não vazia. O padrão executa as 10.000 soluções pedidas na spec:

```sh
.venv/bin/python tst/run_verification.py \
  --suite F \
  --output-dir results/plan-tests/$(date +%F)/F-batch \
  -- \
  --source-result results/plan-tests/$(date +%F)/C/m2-tc5-s101/result.json \
  --count 10000 --chunk-size 1000
```

F compara objetivos, CV e `pair_peaks`, cobre tangências A4/A5, padding, lotes 1/1.000, B1–B9 e registra tempo e speedup.

## 7. Análise estatística

```sh
.venv/bin/python tst/analyze_campaign.py results/plan-tests/$(date +%F)
```

Saídas:

- `analysis.json`: mediana, quartis, Wilcoxon, Kruskal–Wallis, Mann–Whitney e correção de Holm.
- `analysis.md`: tabela compacta de mediana e IQR.
- `blocked.json`: registro explícito de dependências bloqueadas; atualmente vazio.

Interprete C5 como evidência estatística, não como garantia determinística. Compare desempenho batch e escalar apenas em campanhas da mesma revisão, máquina e matriz de parâmetros.

## 8. Execução integral

O lançador integral é deliberadamente protegido porque pode consumir muitas horas:

```sh
TOPICC_CONFIRM_FULL=1 tst/run_all.sh
```

Para usar um rótulo estável em vez da data:

```sh
TOPICC_CONFIRM_FULL=1 TOPICC_TEST_STAMP=paper-final tst/run_all.sh
```

Se uma célula falhar, corrija a causa e repita com os mesmos argumentos e `--resume`. Não apague bundles completos; o `reproduce.sh` de cada célula é a fonte do comando exato.
