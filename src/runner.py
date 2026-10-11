"""Budgeted MOVNS/VND plus a matched KOP-inspired LNS baseline."""
from dataclasses import dataclass
from collections import defaultdict
from time import perf_counter
import random
from .archive import Archive
from .evaluator import Evaluator
from .solution import direct_solution
from .operators import neighbors, normalize, SINGLE_NEIGHBORHOODS, TEAM_NEIGHBORHOODS, ICC_NEIGHBORHOODS


@dataclass
class RunResult:
    problem: object
    config: object
    front: list
    statistics: dict
    elapsed_seconds: float
    status: str
    candidate_bank: tuple = ()
    working_pool: tuple = ()


class Runner:
    def __init__(self,problem,config,allow_team=False):
        self.problem=problem;self.config=config
        self.evaluator=Evaluator(problem,allow_team=allow_team,config=config)
        self.icc=config.mode=="team_kop_icc"
        self.working_pool=[];self.bank=[];self.bank_seen=0
        self.bank_rng=random.Random(config.seed+971)
        self.archive=Archive(config.archive_size,config.eps_reward,config.eps_time)
        self.rng=random.Random(config.seed)
        self.counts=defaultdict(int);self.operator_counts=defaultdict(lambda:defaultdict(int))
        self.seen=set();self.started=0.;self.iterations=0
        families=ICC_NEIGHBORHOODS if self.icc else TEAM_NEIGHBORHOODS if allow_team else SINGLE_NEIGHBORHOODS
        self.families=tuple(n for n in families if n not in config.disabled)
        self.log=[]

    def exhausted(self):
        return self.counts["evaluated"]>=self.config.max_evaluations or perf_counter()-self.started>=self.config.max_seconds

    def evaluate(self,candidate,family):
        self.counts["generated"]+=1;self.operator_counts[family]["generated"]+=1
        if candidate.key in self.seen:
            self.counts["duplicates"]+=1
            return None
        if self.exhausted(): return None
        self.seen.add(candidate.key)
        # Safe axiswise speed lower bound includes stopped waits.
        for m,route in enumerate(candidate.routes):
            bound=sum(v.wait for v in route[:-1])+sum(max(abs(a.position[d]-b.position[d])/self.problem.limits[m].velocity[d] for d in range(2)) for a,b in zip(route,route[1:]))
            if bound>self.problem.time_budgets[m]+1e-8:
                self.counts["screened"]+=1
                return None
        t=perf_counter();result=self.evaluator.evaluate(candidate)
        self.counts["evaluation_seconds"]+=perf_counter()-t
        self.counts["evaluated"]+=1;self.operator_counts[family]["evaluated"]+=1
        if not result.evaluation.valid:
            self.counts["invalid"]+=1
            if result.evaluation.validation_status=="unresolved":self.counts["unresolved"]+=1
            if not (self.icc and result.evaluation.motion_budget_valid):return None
            self._remember(result)
            self.counts["communication_infeasible"]+=1
            if self.config.working_pool_size:
                self.working_pool.append(result)
                self.working_pool.sort(key=lambda s:(s.evaluation.comm_violation,s.objectives,repr(s.key)))
                self.working_pool=self.working_pool[:self.config.working_pool_size]
                return result
            return None
        if self.icc:self._remember(result)
        self.counts["valid"]+=1;self.operator_counts[family]["valid"]+=1
        if self.archive.add(result):
            self.counts["accepted"]+=1;self.operator_counts[family]["accepted"]+=1
            self.log.append({"evaluations":self.counts["evaluated"],"front":len(self.archive.front),"reward":max(s.evaluation.reward for s in self.archive.front)})
        return result

    def _remember(self,solution):
        self.bank_seen+=1
        cap=self.config.candidate_bank_size
        if len(self.bank)<cap:self.bank.append(solution)
        elif cap:
            index=self.bank_rng.randrange(self.bank_seen)
            if index<cap:self.bank[index]=solution

    def cooperative_seed(self,direct,limit):
        current=direct
        if "insert" not in self.families:return current
        while not self.exhausted() and self.counts["evaluated"]<limit:
            best=None;rank=None
            reached=set().union(*current.evaluation.reached_tasks)
            for task in self.problem.tasks:
                if task.id in reached:continue
                from .solution import Visit
                routes=[]
                for m,r in enumerate(current.routes):
                    v=Visit(f"cooperative:{m}:{task.id}","TASK",task.position,(0.,0.),task.id)
                    routes.append(r[:-1]+(v,)+(r[-1],))
                result=self.evaluate(normalize(routes),"cooperative_initialization")
                if result and result.evaluation.valid:
                    gain=result.evaluation.reward-current.evaluation.reward
                    cost=result.objectives[1]-current.objectives[1]
                    score=(gain/max(cost,1e-9),gain,-result.objectives[1])
                    if gain>0 and (rank is None or score>rank):best=result;rank=score
                if self.exhausted() or self.counts["evaluated"]>=limit:break
            if best is None:break
            current=best
        return current

    def construct(self,base,randomized=False,evaluation_limit=None):
        current=base
        while not self.exhausted() and "insert" in self.families:
            if evaluation_limit is not None and self.counts["evaluated"]>=evaluation_limit:break
            best=None;rank=None
            for candidate in neighbors(current,self.problem,self.config,"insert"):
                if self.exhausted():break
                if evaluation_limit is not None and self.counts["evaluated"]>=evaluation_limit:break
                result=self.evaluate(candidate,"construction")
                if result is None:continue
                gain=result.evaluation.reward-current.evaluation.reward
                dt=result.objectives[1]-current.objectives[1]
                score=(float("inf") if dt<=1e-9 and gain>0 else gain/max(dt,1e-9),gain,-result.objectives[1])
                if randomized: score=(score[0]*self.rng.uniform(.7,1.3),*score[1:])
                if gain>0 and (rank is None or score>rank):best=result;rank=score
            if best is None:break
            current=best
        return current

    def shake(self,base,strength):
        current=base
        # Bounded reservoir sample: do not materialize whole neighborhoods.
        for _ in range(strength):
            if self.exhausted() or not self.families:break
            family=self.rng.choice(self.families);chosen=None
            for i,candidate in enumerate(neighbors(current,self.problem,self.config,family),1):
                if self.exhausted():break
                if self.rng.randrange(i)==0:chosen=candidate
                if i>=200:break
            if chosen is not None:
                result=self.evaluate(chosen,family)
                if result is not None:current=result
        return current

    def run(self):
        self.started=perf_counter()
        direct=self.evaluate(normalize(direct_solution(self.problem).routes),"initialization")
        if direct is None:
            return self.finish("no_known_feasible_seed")
        if self.icc:self.cooperative_seed(direct,max(2,self.config.max_evaluations//10))
        self.construct(direct,evaluation_limit=max(2,self.config.max_evaluations//5))
        intensity=1
        for iteration in range(self.config.max_iterations):
            if self.exhausted() or (not self.archive.front and not self.working_pool):break
            self.iterations=iteration+1
            seeds=self.archive.front+self.archive.alternatives
            if self.icc and self.working_pool and (not seeds or self.rng.random()<.5):
                seeds=self.working_pool[:max(1,len(self.working_pool)//2)]
            if self.icc and seeds and self.rng.random()<.2:
                base=min(seeds,key=lambda s:(s.evaluation.comm_violation,s.evaluation.peak_staleness,s.objectives,repr(s.key)))
            else:base=seeds[self.rng.randrange(len(seeds))]
            if self.config.algorithm=="lns":
                route=list(base.routes[0]);number=max(1,int((len(route)-2)*(.5 if iteration<self.config.max_iterations//2 else .2)))
                if "remove" in self.families:
                    for k in sorted(self.rng.sample(range(1,len(route)-1),min(number,len(route)-2)),reverse=True):route.pop(k)
                destroyed=self.evaluate(normalize((tuple(route),)),"lns_destroy")
                if destroyed:self.construct(destroyed,randomized=True)
                continue
            current=self.shake(base,intensity); index=0; improved=False
            families=self.families
            if self.icc and current.evaluation.comm_violation>0:
                communication_families=("meeting","wait","free_move","free_remove")
                families=tuple(n for n in communication_families if n in self.families)+tuple(n for n in self.families if n not in communication_families)
            while index<len(families) and not self.exhausted():
                family=families[index];step=False
                for number,candidate in enumerate(neighbors(current,self.problem,self.config,family)):
                    if self.exhausted() or self.icc and number>=self.config.neighborhood_candidates:break
                    before={s.objectives for s in self.archive.front}
                    result=self.evaluate(candidate,family)
                    guided=(self.icc and result is not None and current.evaluation.comm_violation>0 and
                            (result.evaluation.comm_violation<current.evaluation.comm_violation or
                             result.evaluation.comm_violation==current.evaluation.comm_violation and result.dominates(current)))
                    if result is not None and (guided or result.objectives not in before and any(s.key==result.key for s in self.archive.front)):
                        current=result;step=True;improved=True;break
                index=0 if step else index+1
            intensity=1 if improved else min(4,intensity+1)
        return self.finish("ok" if self.archive.front else "no_communication_feasible_solution")

    def finish(self,status):
        from .trajectory import connect
        from .contacts import pair_contacts
        bank={s.key:s for s in self.bank+list(self.archive.front)+self.working_pool}
        return RunResult(self.problem,self.config,list(self.archive.front),
                         {**dict(self.counts),"iterations":self.iterations,"operators":{k:dict(v) for k,v in self.operator_counts.items()},"log":self.log,
                          "archive_policy":"epsilon_box_dominance","effective_epsilon":self.archive.epsilon,"epsilon_coarsenings":self.archive.coarsenings,
                          "connector_cache":connect.cache_info()._asdict(),"contact_cache":pair_contacts.cache_info()._asdict(),
                          "working_pool_size":len(self.working_pool),"candidate_bank_size":len(bank) if self.icc else 0},perf_counter()-self.started,status,
                         tuple(bank.values()) if self.icc else (),tuple(self.working_pool))
