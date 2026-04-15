"""Main optimization loop for MOVNS."""

import time
from tqdm import tqdm

from topcc.archive import Archive
from topcc.evaluator import Evaluator
from topcc.operators import Neighborhood, local_search, perturb_solution
from topcc.solution import Solution


class Runner:

    def __init__(
        self,
        max_time: float,
        max_iterations: int,
        archive: Archive,
        neighborhood: Neighborhood,
        environment,
        evaluator: Evaluator,
        problem_ctx,
    ):
        self.archive = archive
        self.env = environment
        self.max_iterations = max_iterations
        self.max_time = max_time
        self.neighborhood = neighborhood
        self.evaluator = evaluator
        self.ctx = problem_ctx
        self.log = []

    def run(self):
        start_time = time.perf_counter()

        initial_solution = Solution(
            ctx=self.ctx, distmx=self.env.distmx, rvalues=self.env.rvalues
        )
        self.evaluator.evaluate(initial_solution)

        for neighborhood_id in tqdm(
            range(self.neighborhood.num_neighborhoods),
            desc="Initial local search",
            unit="neighborhood",
            dynamic_ncols=True,
        ):
            neighbors = local_search(initial_solution, self.neighborhood, neighborhood_id)
            self.evaluator.evaluate(neighbors)
            self.archive.update_archive(neighbors)

        progress_bar = tqdm(
            total=self.max_iterations, desc="Progress", unit="it", dynamic_ncols=True
        )
        iteration = 0

        while iteration < self.max_iterations and time.perf_counter() - start_time < self.max_time:
            solution = self.archive.select_solution_to_optimize(iteration)

            for neighborhood_id in range(self.neighborhood.num_neighborhoods):
                if time.perf_counter() - start_time > self.max_time:
                    break

                perturbed = perturb_solution(solution, self.neighborhood)
                neighbors = local_search(perturbed, self.neighborhood, neighborhood_id)

                new_solutions = [perturbed] + neighbors
                self.evaluator.evaluate(new_solutions)
                self.archive.update_archive(new_solutions)
                self._save_statistics()

            iteration += 1
            progress_bar.update(1)

        progress_bar.close()
        elapsed_time = time.perf_counter() - start_time
        return self.log, elapsed_time

    def _save_statistics(self):
        if not self.archive.front:
            return
        max_reward = max(s.score[0] for s in self.archive.front)
        max_rssi = max(s.score[1] for s in self.archive.front)
        self.log.append([max_reward, max_rssi])
