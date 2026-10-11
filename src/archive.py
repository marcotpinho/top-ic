"""Strict two-objective front with crowding and alternate exploration seeds."""
class Archive:
    def __init__(self,max_size=40):
        self.max_size=max_size
        self.front=[]
        self.alternatives=[]

    def add(self,solution):
        if not solution.evaluation or not solution.evaluation.valid:
            return False
        if any(s.key==solution.key for s in self.front+self.alternatives):
            return False
        if any(s.dominates(solution) for s in self.front):
            return False
        if any(s.objectives==solution.objectives for s in self.front):
            self.alternatives=(self.alternatives+[solution])[-self.max_size:]
            return False
        self.front=[s for s in self.front if not solution.dominates(s)]
        self.front.append(solution)
        self.front.sort(key=lambda s:s.objectives)
        if len(self.front)>self.max_size:
            self._trim()
        # Alternatives are exploration only, never reported as front points.
        self.alternatives=[s for s in self.alternatives if not any(f.dominates(s) for f in self.front)]
        return any(s.key==solution.key for s in self.front)

    def _trim(self):
        distances={s.key:0. for s in self.front}
        for d in range(2):
            ordered=sorted(self.front,key=lambda s:s.objectives[d])
            lo,hi=ordered[0].objectives[d],ordered[-1].objectives[d]
            distances[ordered[0].key]=distances[ordered[-1].key]=float("inf")
            if hi>lo:
                for i in range(1,len(ordered)-1):
                    distances[ordered[i].key]+=(ordered[i+1].objectives[d]-ordered[i-1].objectives[d])/(hi-lo)
        worst=min(range(len(self.front)),key=lambda i:(distances[self.front[i].key],-i))
        self.front.pop(worst)
