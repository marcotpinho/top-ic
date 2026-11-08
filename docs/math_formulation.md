# Team KOP-ICC — Mathematical Formulation

Target formulation for a metaheuristic, following [variables](variables.md) and the [model contract](../spec/00-model-contract.md). This defines feasible solutions and evaluation; it is not a MILP. The implementation stages are single-agent KOP, team KOP, and team KOP with intermittent communication/free waypoints.

## 1. Inputs and motion convention

Let $\mathcal V=\{1,\ldots,N\}$ be reward tasks with positions $z_i\in\mathbb R^2$ and rewards $r_i\ge0$. Agents $\mathcal A=\{1,\ldots,M\}$ share start $z_S$ and destination $z_E$. Each has flight-time budget $B_m>0$, initial velocity $v_m^S$, and positive axis bounds $\bar v_{md},\bar a_{md}$ for $d\in\{x,y\}$. Final velocity is zero.

The proposed KOP-compatible convention is componentwise bounds, not magnitude bounds. Default initial velocity is zero. Collisions are ignored; crossing and co-location are permitted. No obstacle or jerk constraints are imposed in this version.

Communication parameters, required only in the final stage, are range $R>0$, handshake duration $\delta\ge0$, and window length $T_c>0$.

## 2. Visit sequences and motion states

Agent $m$ selects a finite ordered sequence of visit occurrences

$$
\pi_m=(\nu_{m0},\ldots,\nu_{m,K_m-1}),\qquad K_m\ge2.
$$

The first occurrence is START at $z_S$ and the last is END at $z_E$. Interior occurrences are TASK or, in the communication stage, FREE. Each visit has position $z_{mk}$ and boundary velocity $v_{mk}$. A TASK occurrence referencing $i$ satisfies $z_{mk}=z_i$; a FREE occurrence has adjustable coordinates and no intrinsic reward.

Repeated task occurrences and shared visits are allowed. Start and end are different occurrence kinds even when their coordinates coincide. The final END is terminal: agents cannot leave it afterward. A zero-task route still must reach END.

$$
v_{m0}=v_m^S,\qquad v_{m,K_m-1}=0. \tag{1}
$$

The initial search uses a finite admissible visit-velocity menu $v_{mk}\in\mathcal U_m$, apart from prescribed endpoints. This is an implementation restriction on the continuous problem. Free-position workspace bounds are likewise explicit search restrictions. The search imposes no cap on the number of FREE visits per agent.

## 3. Continuous trajectories and timing

Connect consecutive visit states with feasible motion of duration $D_{mk}\ge0$. The initial constructor uses deterministic minimum-time connections; edited velocity states and route geometry provide timing flexibility. If a longer prescribed duration is introduced, its dynamics must be revalidated rather than obtained by naive time scaling.

Arrival and departure satisfy

$$
\alpha_{m0}=0,\qquad
\beta_{mk}=\alpha_{mk},\qquad
\alpha_{m,k+1}=\beta_{mk}+D_{mk}. \tag{2}
$$

Arrival and departure coincide at every visit. Each moving connection starts at $(z_{mk},v_{mk})$ and ends at $(z_{m,k+1},v_{m,k+1})$.

Motion obeys

$$
\dot p_m(t)=v_m(t),\qquad \dot v_m(t)=a_m(t),\qquad
|v_{md}(t)|\le\bar v_{md},\quad |a_{md}(t)|\le\bar a_{md}. \tag{3}
$$

The implementation represents motion by finitely many constant-acceleration pieces. On piece $q$ with absolute start $\theta_{mq}$ and local $\tau\in[0,h_{mq}]$,

$$
p_m(\theta_{mq}+\tau)=p^0_{mq}+v^0_{mq}\tau+\tfrac12a_{mq}\tau^2,
\qquad
v_m(\theta_{mq}+\tau)=v^0_{mq}+a_{mq}\tau. \tag{4}
$$

Adjacent pieces agree in position and velocity; acceleration may jump. Positive-duration pieces have $h_{mq}>0$; canonical construction removes zero-duration pieces. A zero-duration connection between identical states is allowed, including a direct empty route at coincident start/end with zero velocity. All piece bounds and prescribed visit passages must hold continuously, not merely at sampled frames.

## 4. Expenditure and terminal presence

$$
c_m=\alpha_{m,K_m-1}=\sum_{k=0}^{K_m-2}D_{mk},\qquad
c_m\le B_m,\qquad
T=\max_m c_m,\qquad
\bar c=\frac1M\sum_m c_m. \tag{5}
$$

Thus travel before final arrival consumes budget; routes contain no explicit pauses. For communication evaluation, extend each trajectory by

$$
p_m(t)=z_E,\qquad v_m(t)=0,\qquad a_m(t)=0
\quad\text{for }t\in[c_m,T]. \tag{6}
$$

This extension does not increase $c_m$ or budget expenditure. The mean $\bar c$ is different from mission duration $T$.

## 5. Rewards and objectives

Define credited tasks from explicit TASK occurrences by

$$
\mathcal Q_m=\{i\in\mathcal V:\exists k,\ \kappa_{mk}=\mathrm{TASK},\ \iota_{mk}=i\},\qquad
Q=\sum_{i\in\bigcup_m\mathcal Q_m}r_i. \tag{7}
$$

Stopping is not necessary for reward collection: an explicit TASK occurrence may have nonzero velocity. A task contributes once regardless of repeated/shared visits. Incidental trajectory crossings and FREE visits at a task's coordinates do not earn reward. TASK positions are checked exactly against the declared task coordinates; continuous motion must pass through each declared visit.

The reported objective vector is

$$
f(S)=(-Q,\bar c). \tag{8}
$$

Communication feasibility is imposed through (15), not through a third objective. There is no objective for path length, RSSI, or mission duration. Path length $L_m=\int_0^{c_m}\|v_m(t)\|\,dt$ is a diagnostic. Flight time is the expenditure proxy; no physical energy claim is made.

## 6. Contacts and usable links

For $m\ne n$, let

$$
\mathcal C_{mn}=\{t\in[0,T]:\|p_m(t)-p_n(t)\|\le R\}. \tag{9}
$$

On overlapping constant-acceleration pieces, relative position is quadratic in local time; squared separation minus $R^2$ is a polynomial of degree at most four. Its nonpositive set can contain several intervals or isolated instants. Merge continuous contact across all piece boundaries into maximal closed intervals before applying the handshake.

Let $\mathcal J_{mn}$ denote those maximal intervals. With initial handshakes and synchronization completed before departure,

$$
\mathcal I_{mn}=
\bigcup_{[0,e]\in\mathcal J_{mn}}[0,e]
\ \cup\!
\bigcup_{\substack{[s,e]\in\mathcal J_{mn}\\s>0,\ e-s\ge\delta}}[s+\delta,e]. \tag{10}
$$

A later interruption resets the handshake. Equality $e-s=\delta$ gives a point link; $\delta=0$ permits instantaneous range-touch links. An initial interval remains usable even if shorter than $\delta$.

$$
\mathcal E(t)=\{\{m,n\}:m<n,\ t\in\mathcal I_{mn}\},\qquad
\mathcal G(t)=(\mathcal A,\mathcal E(t)). \tag{11}
$$

Connected components exchange information instantaneously. Agents retain received information and forward it later, including after arrival at END.

## 7. Temporal propagation and recurrence

A journey from $m$ to $n$ is a sequence $m=k_0,k_1,\ldots,k_\ell=n$ with link times $t_1\le\cdots\le t_\ell$, each $\{k_{j-1},k_j\}\in\mathcal E(t_j)$. Non-strict time ordering permits simultaneous multi-hop relay.

For $m\ne n$, define latest information timestamp and staleness as

$$
h_{nm}(\sigma)=\max\bigl(\{0\}\cup\{t_1:\text{a journey }m\to n\text{ arrives by }\sigma\}\bigr),
\qquad A_{nm}(\sigma)=\sigma-h_{nm}(\sigma). \tag{12}
$$

Initial synchronization supplies the timestamp zero. For propagation bookkeeping use $h_{mm}(\sigma)=\sigma$.

$$
\Delta=\begin{cases}
\displaystyle\sup_{\sigma\in[0,T]}\max_{m\ne n}A_{nm}(\sigma),&M\ge2,\\
0,&M=1.
\end{cases}
\tag{13}
$$

The supremum accounts for unattained peaks immediately before an exchange. A reported $T_c$ slice requires $\Delta\le T_c$; equivalently every full sliding window must support all-to-all propagation:

$$
\forall t\ge0\text{ with }t+T_c\le T,\ \forall m\ne n:
\exists\text{ a journey }m\to n\text{ with }t_1\ge t,\ t_\ell\le t+T_c. \tag{14}
$$

Under initial synchronization, (13) and (14) are equivalent: for $\sigma\ge T_c$, take $t=\sigma-T_c$ and require $h_{nm}(\sigma)\ge t$; before $T_c$, $h_{nm}\ge0$ already bounds age. Conversely the age bound at $t+T_c$ supplies a departure timestamp at least $t$. If $T<T_c$, no full window exists and initial timestamps bound every age by $T<T_c$.

Only full windows inside the mission are imposed. No extra delivery requirement applies to information generated near termination, and final co-location does not waive a handshake.

## 8. Evaluation and search semantics

A chronological sweep uses effective-link endpoints plus $0,T$. For each steady open segment, advance member-source timestamps through its connected components. At a breakpoint, record the preceding graph's left-limit ages, then exchange componentwise latest timestamps through all links present at that exact instant, including point links and links ending there. Process the next steady graph separately. Evaluating only post-exchange ages can underestimate $\Delta$.

Define ordered-pair communication violation

$$
CV(S)=\sum_{n\ne m}\max(0,P_{nm}(S)-T_c),
\qquad P_{nm}=\sup_{t\in[0,T]}A_{nm}(t). \tag{15}
$$

Because $\Delta=\max_{n\ne m}P_{nm}$, $CV=0$ if and only if $\Delta\le T_c$. The reported minimization vector is $(-Q,\bar c)$. `CV`, the integrated excess $A_c$, and every individual $P_{nm}$ are constraint values or diagnostics, never objectives. Each $T_c$ requires its own optimization run.

For diagnostics, let
$$
A_c=\sum_{n\ne m}\int_0^T [A_{nm}(t)-T_c]_+\,dt.
$$
The chronological sweep computes $P_{nm}$ and integrates the positive part of each affine age segment between communication events. These diagnostics can distinguish partial repairs whose global $\Delta$ is unchanged. They do not change (15) or archive feasibility.

Communication contacts are determined entirely by the agents' evaluated trajectories. Every valid moving or stationary contact contributes to (9)–(14); no separate rendezvous decision is stored.

For fixed trajectories, $\Delta$ is independent of $T_c$, and communication feasibility is monotone as $T_c$ increases. An edit that changes trajectories can change encounter order and staleness anywhere downstream. Removing communication recovers the team KOP variant with time budgets, not constant-speed TOP.

Numerical quartic contact extraction needs documented tolerances and uncertainty handling. Complexity and exactness claims must follow the implemented verifier; the earlier constant-speed sweep bounds are not assumed here. The mathematical model is continuous in time even though visit velocities may be discretized by the search.

## Implementation status

See [implementation milestones](implementation.md) for supported stages, validation, and commands. The current ICC code implements continuous communication from evaluated trajectories and optional FREE waypoints; see the milestone record for supported numerical policies and limits.

Single-agent implementation: MOVNS and the five named KOP neighborhoods are available; see [step 2 status](implementation.md#step-2--single-agent-movns-kop). Team assignment operators are now implemented on the step 3 branch; communication is implemented on the step 4 branch.

Team implementation: individual time budgets, shared reward accounting, and cross-agent assignment moves are available; see [step 3 status](implementation.md#step-3--multi-agent-kop). Collision constraints remain ignored. Communication and FREE visits are always enabled.

## Epsilon-dominance archive policy

The feasible archive `F` contains only solutions satisfying movement, budget and $CV=0$. With $f=(-Q,\bar c)$ and widths $(1,0.1\,\mathrm{s})$, define $b_i=\lfloor f_i/\varepsilon_i\rfloor$. Retain nondominated boxes and one representative per box, chosen by minimum squared normalized distance to its lower corner. If more than 100 representatives remain, double both widths and refilter.

The coverage pool `P` contains valid candidates outside `F`, has capacity 100 and associates candidates to 21 uniform weight vectors in normalized reward–time space. C-TAEA-style coverage rounds use Tchebycheff selection relative to the ideal of `F`; ties use lower `CV`. Pool age removes a member after more than five consecutive expansions without improvement. Feasibility does not enter the coverage decision. Saved statistics record effective widths, coverage, age and coarsening.

Normalize a candidate for coverage as $(1-Q/Q_{\mathrm{total}},\bar c/B_{\max})$ and associate it with the smallest-angle vector in $\{(i/20,1-i/20):i=0,\ldots,20\}$. Let $n_k$ be the number of members of `F` in subregion $k$. In coverage round $itr$, that region admits at most $itr-n_k$ pool members. Fill each available position with an objective-nondominated candidate of minimum Tchebycheff value relative to the ideal of `F`, breaking ties by `CV` and then a stable decision key. Repeat rounds until `P` reaches capacity or no candidate remains.

For base selection, construct $ND_F$ by Pareto dominance in $(-Q,\bar c)$ inside `F`, and construct $ND_P$ by three-dimensional Pareto dominance in $(CV,-Q,\bar c)$ inside `P`. Let $n_F=|ND_F|$ and $n_P=|ND_P|$. Select `P` with probability $\rho_P=n_P/(n_F+n_P)$ and `F` with probability $\rho_F=1-\rho_P$; an empty archive has probability zero. Tournament participants are sampled only from the selected nondominated set. In `ND_F`, larger two-objective crowding wins. In `ND_P`, lower `CV` wins, breaking ties by larger $Q$, lower $\bar c$, and a stable decision key.

One iteration applies a seeded 10–40% ruin to the selected base and regret-2 recreation, followed by at most three best-improvement communication-repair rounds when `CV` is positive. Repair considers bounded invitation candidates that insert FREE visits without pauses and stops when a round cannot strictly reduce `CV`. VND then evaluates each distinct candidate exactly and sends every valid result through the `F` and `P` updates. The primary comparison budget is the number of exact evaluator cache misses.

## Step 4 implementation

`team_kop_icc` implements quartic range-contact extraction, maximal-interval handshake handling, initial synchronization, simultaneous connected-component relay, and vector-clock staleness with left limits. An independent reverse temporal-reachability oracle validates propagation. Near-multiple roots that cannot be resolved under the numerical policy are rejected rather than admitted as feasible.

Consecutive fixed route connections determine visit times, with identical arrival and departure times at every visit. Travel is charged until each agent's final arrival. Free positions are bounded by the configured workspace and per-agent visit cap.

The current ICC search uses the feasible archive `F` and coverage pool `P` defined above. Ruin-and-recreate precedes bounded communication repair and VND. Every distinct candidate is evaluated exactly and routed through both archive update rules.

Current ICC results use schema version 7 and publish only `F`, with pool, repair, cache and evaluation-indexed health diagnostics in statistics. Historical schemas retain their original meaning.
