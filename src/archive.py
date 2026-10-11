"""Two-objective epsilon-box dominance; no crowding-distance truncation.

Each nondominated box retains the point closest to its lower corner. If a
capacity is requested, deterministically double both box widths until the
box front fits. Effective widths are recorded for honest result reporting.
"""
from math import floor,isfinite


class Archive:
    def __init__(self,max_size=40,eps_reward=1.0,eps_time=0.1):
        if max_size<1 or not all(isfinite(e) and e>0 for e in (eps_reward,eps_time)):
            raise ValueError('Archive capacity and epsilon widths must be positive')
        self.max_size=max_size
        self.epsilon=(float(eps_reward),float(eps_time))
        self.front=[]
        self.alternatives=[]
        self.coarsenings=0

    def box(self,solution):
        return tuple(floor(f/e) for f,e in zip(solution.objectives,self.epsilon))

    @staticmethod
    def box_dominates(a,b):
        return all(x<=y for x,y in zip(a,b)) and any(x<y for x,y in zip(a,b))

    def representative_key(self,solution):
        box=self.box(solution)
        distance=sum((f/e-b)**2 for f,e,b in zip(solution.objectives,self.epsilon,box))
        delta=solution.evaluation.peak_staleness
        return (distance,solution.objectives,float("inf") if delta is None else delta,repr(solution.key))

    def _filter(self,solutions):
        representatives={}
        for s in solutions:
            box=self.box(s)
            if box not in representatives or self.representative_key(s)<self.representative_key(representatives[box]):
                representatives[box]=s
        boxes=list(representatives)
        return sorted((representatives[b] for b in boxes if not any(self.box_dominates(other,b) for other in boxes)),key=lambda s:s.objectives)

    def add(self,solution):
        if not solution.evaluation or not solution.evaluation.valid:
            return False
        if any(s.key==solution.key for s in self.front+self.alternatives):
            return False
        old=self.front[:]
        self.front=self._filter(old+[solution])
        while len(self.front)>self.max_size:
            self.epsilon=tuple(e*2 for e in self.epsilon)
            self.coarsenings+=1
            self.front=self._filter(self.front)
        retained=any(s.key==solution.key for s in self.front)
        # Preserve only objective-equal alternatives, outside the epsilon front.
        for s in old+[solution]:
            if not any(f.key==s.key for f in self.front) and any(f.objectives==s.objectives for f in self.front):
                if not any(a.key==s.key for a in self.alternatives):self.alternatives.append(s)
        self.alternatives=[s for s in self.alternatives if any(f.objectives==s.objectives for f in self.front)][-self.max_size:]
        return retained
