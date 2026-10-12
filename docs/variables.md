# Team KOP-ICC — Variable Glossary

Notation for the target model, following [modeling](modeling.md) and the [implementation contract](../spec/00-model-contract.md). Code names below are proposed interfaces, not claims about the current code.

## Index conventions

| Math | Meaning |
|---|---|
| $i,j$ | Fixed task IDs |
| $m,n$ | Agent indices |
| $k$ | Visit occurrence index within an agent's ordered route |
| $q$ | Constant-acceleration trajectory-piece index |
| $d$ | Coordinate axis, $x$ or $y$ |

Visit occurrences have stable IDs separate from route positions. Repeated visits to one task have distinct occurrences. Communication timestamps use $\sigma$; local time within a motion piece uses $\tau$.

## Inputs

| Math | Meaning | Unit/type | Proposed code name |
|---|---|---|---|
| $\mathcal V=\{1,\ldots,N\}$ | Reward tasks, excluding depots | Task IDs | `tasks` |
| $z_i$ | Position of task $i$ | 2D distance | `task.position` |
| $r_i$ | Reward of task $i$ | Nonnegative scalar | `task.reward` |
| $z_S,z_E$ | Common start and destination positions | 2D distance | `start_position`, `end_position` |
| $\mathcal A=\{1,\ldots,M\}$ | Agents | IDs | `agents` |
| $B_m$ | Flight-time budget | Time | `time_budget[m]` |
| $\bar v_{md}$ | Maximum absolute velocity component | Distance/time | `velocity_axis_limit[m][d]` |
| $\bar a_{md}$ | Maximum absolute acceleration component | Distance/time² | `acceleration_axis_limit[m][d]` |
| $v_m^S$ | Initial velocity; zero default | 2D distance/time | `initial_velocity[m]` |
| $\mathcal U_m$ | Finite visit-velocity menu used initially by search | 2D vectors | `visit_velocity_states[m]` |
| $\mathbb W$ | Configured free-waypoint search workspace | Bounds | `waypoint_workspace` |
| $F_{\max}$ | Algorithmic free-visit cap per agent | Count | `max_free_waypoints` |
| $R$ | Euclidean communication range | Distance | `comm_range` |
| $\delta$ | Required continuous handshake duration | Time | `handshake_time` |
| $T_c$ | Sliding-window recurrence bound | Time | `recurrence_bound` |

The initial convention uses componentwise limits. A diagonal vector can have magnitude greater than one axis limit. $\mathcal U_m$, $\mathbb W$, and $F_{\max}$ restrict the search representation; they are not assertions about the unrestricted continuous optimum. Budgets and bounds are identical initially but retain agent indexing. Final velocity is zero in this version.

## Solution decisions

| Math | Meaning | Proposed code name |
|---|---|---|
| $\pi_m$ | Ordered START/TASK/FREE/END visit occurrences | `agent_plan.visits` |
| $K_m$ | Number of visit occurrences | `num_visits` |
| $\kappa_{mk}$ | Visit kind | `visit.kind` |
| $\iota_{mk}$ | Task ID when the visit is TASK | `visit.task_id` |
| $z_{mk}$ | Visit position; fixed for tasks, adjustable for FREE | `visit.position` |
| $v_{mk}$ | Arrival/departure boundary velocity | `visit.velocity` |
| $w_{mk}$ | Pre-departure wait; positive only at zero velocity | `visit.wait_duration` |
| $\mathcal P$ | Optional planned meetings between stable visit IDs | `planned_meetings` |
| $D_{mk}$ | Duration of motion connecting visit $k$ to $k+1$ | `connection.duration` |
| $h_{mq}$ | Duration of constant-acceleration piece $q$ | `piece.duration` |
| $a_{mq}$ | Acceleration vector on piece $q$ | `piece.acceleration` |

Connector-generated durations/accelerations are derived from endpoint states in the initial implementation. If explicit duration/profile choices are later introduced, they become stored decisions and part of solution identity. Wait at terminal END is zero; post-arrival stationary presence is derived separately.

## Derived trajectories, rewards, and expenditure

| Math | Meaning | Proposed code name |
|---|---|---|
| $\alpha_{mk},\beta_{mk}$ | Visit arrival/departure times | `arrival_time`, `departure_time` |
| $\theta_{mq}$ | Absolute start time of piece $q$ | `piece.start_time` |
| $p_m(t),v_m(t),a_m(t)$ | Position, velocity, acceleration | `position`, `velocity`, `acceleration` |
| $c_m$ | Final arrival time and budget expenditure | `completion_time[m]` |
| $\bar c$ | Mean completion time | `mean_completion_time` |
| $T$ | Mission horizon, $\max_m c_m$ | `mission_horizon` |
| $\mathcal Q_m$ | Task IDs in agent $m$'s explicit TASK visits | `reached_tasks[m]` |
| $Q$ | Team reward over $\bigcup_m\mathcal Q_m$ | `total_reward` |
| $L_m$ | Integrated path length; diagnostic only | `path_length[m]` |

Use occurrence-indexed arrival times, never one time per task per agent. Waiting before final arrival counts toward $c_m$. Presence at the destination on $[c_m,T]$ contributes to communication without increasing $c_m$.

## Communication and evaluation

| Math | Meaning | Proposed code name |
|---|---|---|
| $\mathcal C_{mn}$ | Raw range-contact set, maximal closed intervals | `contacts[m][n]` |
| $[s,e]$ | One maximal contact, possibly a single instant | `contact.start`, `contact.end` |
| $\mathcal I_{mn}$ | Effective intervals after handshake/initial exception | `effective_contacts[m][n]` |
| $\mathcal G(t),\mathcal E(t)$ | Instantaneous graph and effective links | `comm_graph_at`, `active_links` |
| $h_{nm}(\sigma)$ | Latest source timestamp from $m$ held by $n$ | `latest_departure[n][m]` |
| $A_{nm}(\sigma)$ | Staleness $\sigma-h_{nm}(\sigma)$ | `staleness[n][m]` |
| $\Delta$ | Supremum of off-diagonal staleness; zero if $M=1$ | `peak_staleness` |
| $V_c$ | Communication violation $\max(0,\Delta-T_c)$ | `comm_violation` |
| $P_{nm}$ | Peak information age for directed source $m$ to receiver $n$; diagnostic only | `communication.pair_peaks[n][m]` |
| $A_c$ | Sum over directed pairs of time-integrated age above $T_c$; search guidance only | `communication.integrated_excess` |
| $V_{b,m}$ | Budget excess $\max(0,c_m-B_m)$ | `budget_excess[m]` |
| $C$ | Total effective interval count | `num_links` |
| $J$ | Breakpoint count, at most $2C+2$ before deduplication | `num_breakpoints` |
| — | Steady links on an open breakpoint segment | `steady_links` |
| — | All links present at an exact breakpoint | `active_links_now` |
| — | Root/residual/time/position tolerance policy | `numerical_policy` |
| — | Valid, invalid, or numerically unresolved trajectory/evaluation | `validation_status` |

Keep handshake $\delta$ and staleness $\Delta$ distinct in code. Effective initial contact $[0,e]$ needs no new handshake; later effective contact is $[s+\delta,e]$ when $e-s\ge\delta$.

## Objectives and search

| Math/concept | Meaning | Proposed code name |
|---|---|---|
| $f_1=-Q$ | Reward objective in minimization form | `objectives[0]` |
| $f_2=\bar c$ | Expenditure objective | `objectives[1]` |
| $f_3=V_c=\max(0,\Delta-T_c)$ | ICC violation objective | `objectives[2]` |
| — | Physically valid epsilon-box nondominated front in three ICC objectives | `archive` |
| — | Valid dominated search seeds with crowding-distance truncation | `dominated_archive` |

## Step 4 implementation

`team_kop_icc` implements quartic range-contact extraction, maximal-interval handshake handling, initial synchronization, simultaneous connected-component relay, and vector-clock staleness with left limits. An independent reverse temporal-reachability oracle validates propagation. Near-multiple roots that cannot be resolved under the numerical policy are rejected rather than admitted as feasible.

Meetings reference preserved visit occurrences. A least-schedule difference-constraint solver detects positive cycles and adds stopped waits, charged until each agent's final arrival. Free positions are bounded by the configured workspace and per-agent visit cap. Five communication-stage operator families are `wait`, `meeting`, `duplicate_rendezvous`, `free_move`, and `free_remove`. Existing task and assignment families remain available.

The current ICC epsilon archive uses negative reward, mean completion time, and communication violation at the configured $T_c$. Valid motion and individual budgets determine archive eligibility; the reported reward–time front is its zero-violation slice. A separate bounded dominated-solution archive uses normalized crowding distance to preserve diverse search seeds. Full propagation is recomputed; pair-contact caching includes the mission horizon. Checkpointed incremental propagation is deferred.

Current ICC results use schema version 4 and include full routes, meetings, actual visit times, trajectories, raw/effective contacts, staleness traces, a three-objective archive, a dominated archive, accepted-front snapshots, and zero-violation front indices. Historical stage-4 files remain schema versions 2 or 3. ICC VND examines at most 120 candidates per family per pass by default; these are search restrictions, not completeness guarantees.
