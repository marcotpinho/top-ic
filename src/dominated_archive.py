"""Bounded structural reservoir for solutions outside the epsilon front.

Crowding distance is used only here, never to filter the nondominated front.
"""
from math import inf


def repair_coordinates(solution):
    """Auxiliary diversity axes; the official Pareto objectives are unchanged."""
    comm=solution.evaluation.communication
    if comm is None or solution.objectives[2]<=0:
        return (0.,0.)
    peaks=sorted((value for receiver,row in enumerate(comm.pair_peaks)
                  for source,value in enumerate(row) if source!=receiver),reverse=True)
    return (comm.integrated_excess,peaks[1] if len(peaks)>1 else 0.)


class DominatedArchive:
    def __init__(self, max_size):
        if max_size < 0:
            raise ValueError("Dominated archive capacity must be nonnegative")
        self.max_size = max_size
        self.solutions = []

    @staticmethod
    def distances(solutions):
        scores = {s.key: 0.0 for s in solutions}
        if len(solutions) <= 2:
            return {s.key: inf for s in solutions}
        coordinates={s.key:(*s.objectives,*repair_coordinates(s)) for s in solutions}
        for coordinate in range(len(solutions[0].objectives)+2):
            ordered = sorted(solutions, key=lambda s: (coordinates[s.key][coordinate], repr(s.key)))
            low, high = coordinates[ordered[0].key][coordinate], coordinates[ordered[-1].key][coordinate]
            scores[ordered[0].key] = scores[ordered[-1].key] = inf
            if high > low:
                for before, current, after in zip(ordered, ordered[1:], ordered[2:]):
                    if scores[current.key] != inf:
                        scores[current.key] += (coordinates[after.key][coordinate] - coordinates[before.key][coordinate]) / (high - low)
        return scores

    def add(self, solution, front=()):
        if not self.max_size or not solution.evaluation or not solution.evaluation.valid:
            return False
        front_keys = {s.key for s in front}
        if solution.key in front_keys or any(s.key == solution.key for s in self.solutions):
            return False
        self.solutions.append(solution)
        self.solutions = [s for s in self.solutions if s.key not in front_keys]
        while len(self.solutions) > self.max_size:
            scores = self.distances(self.solutions)
            worst = min(self.solutions, key=lambda s: (scores[s.key], s.objectives, repr(s.key)))
            self.solutions.remove(worst)
        return any(s.key == solution.key for s in self.solutions)
