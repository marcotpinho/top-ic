# Plano de migração para o conector KOP e ablação C

## Objetivo

Substituir o perfil de aceleração obtido por interpolação dos envelopes alcançáveis pelos padrões analíticos do Kinematic Orienteering Problem (KOP), preservando as decisões específicas do TOP-ICC: múltiplos agentes, headings geométricos, magnitudes de velocidade variáveis, waypoints `FREE` e comunicação intermitente.

## Alteração cinemática

Para cada eixo e duração comum candidata, enumerar:

- padrões clássicos `(A, 0, -A)`, com `A` positivo e negativo;
- padrões de sincronização `(A, 0, A)`, com `A` positivo e negativo;
- todas as raízes analíticas admissíveis das durações das fases.

Um padrão é admissível quando suas durações são não negativas, as velocidades permanecem dentro dos limites por eixo e os resíduos de posição e velocidade finais estão dentro da tolerância numérica.

As fronteiras analíticas dos intervalos alcançáveis fornecem as durações candidatas. A menor duração que admite ao menos um padrão KOP em cada eixo é selecionada. Não usar busca binária, pois o conjunto de durações factíveis pode ser desconectado.

Quando mais de um perfil for admissível, usar uma ordem determinística: padrões clássicos antes dos padrões de sincronização, aceleração positiva antes da negativa e primeira raiz admissível. A versão do conector deve ser registrada no resultado.

## Escopo preservado

- Manter headings interiores derivados da geometria da rota.
- Manter as frações de velocidade como variáveis da busca.
- Manter limites de velocidade e aceleração por eixo.
- Manter continuidade de posição e velocidade.
- Manter aceleração constante por partes e jerk ilimitado nos switches.
- Não implementar a tabela completa do KOP, pois os waypoints `FREE` são contínuos.
- Manter cache sob demanda das primitivas.

## Validação de execução

Executar primeiro um piloto curto exclusivamente por `scripts/run_experiment.py`. Confirmar no JSON e no log:

- status `ok`;
- fronteira não vazia;
- `connector_version` KOP;
- ausência de `MotionError`;
- acelerações de cada componente limitadas a `-A`, `0` ou `+A`, dentro da tolerância;
- artefatos completos e README criado pelo template.

Não criar nem executar testes unitários.

## Campanha C

Executar o mapa M2 para:

- `Tc ∈ {0.05, 2, 5, 10, 100}`;
- seeds `101`, `102` e `103`;
- `max_seconds = 900`;
- `max_evaluations = 1_000_000`;
- avaliação batch;
- três processos de campanha concorrentes;
- cada processo protegido por `caffeinate -i` e vinculado à sua execução.

Salvar o braço KOP em `results/2026-11-15/kop/C/`, no mesmo padrão de bundles de `results/`.

## Braço de referência

Usar como referência pareada os 15 resultados envelope com headings geométricos em `results/2026-11-13/C/`. Eles possuem o mesmo mapa, valores de `Tc`, seeds, tempo máximo, operadores e política de seleção. Registrar a revisão de cada braço na análise.

## Análise de ablação

Para cada par `(Tc, seed)`, extrair:

- maior recompensa factível;
- menor tempo médio entre soluções com recompensa máxima;
- tamanho da fronteira;
- número de avaliações exatas;
- avaliações por segundo;
- tempo de construção de trajetórias;
- violação de comunicação e pico de staleness da solução escolhida;
- quantidade e duração das peças de trajetória;
- frequência de componentes de aceleração intermediárias.

Consolidar por `Tc` com média, mediana, desvio-padrão e diferenças pareadas KOP menos envelope. Separar qualidade de solução de throughput, pois as execuções são limitadas por tempo.

Salvar em `results/2026-11-15/kop-ablation/`:

- tabela pareada em JSON e CSV;
- resumo agregado em JSON;
- relatório em Markdown;
- gráficos de recompensa, tempo e throughput por `Tc`;
- script de análise e comando exato de reprodução;
- README baseado em `docs/templates/README.md`, preenchido com o escopo da análise.

## Critérios de decisão

Recomendar o KOP como conector principal se:

- todas as execuções forem válidas;
- não houver regressão sistemática de recompensa em `Tc`;
- o custo computacional permanecer compatível com a campanha;
- os perfis forem estritamente bang-zero-bang;
- a mudança simplificar a justificativa metodológica sem prejudicar a coordenação.

Caso contrário, manter o conector envelope como principal e apresentar o KOP como ablação ou baseline cinemático.
