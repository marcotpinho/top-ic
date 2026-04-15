"""MOVNS solver orchestration: the top-level entry point for optimization."""

import random
import pickle
import numpy as np
from pathlib import Path

from topcc.config import Config, ProblemContext
from topcc.archive import Archive
from topcc.evaluator import Evaluator
from topcc.runner import Runner
from topcc.environment import Map2D
from topcc.operators import Neighborhood


def run_optimization(
    rpositions: np.ndarray,
    rvalues: np.ndarray,
    budget: list[float],
    map_name: str,
    num_agents: int,
    speeds: list[float],
    config: Config,
    begin: int = -1,
    end: int = -2,
) -> list:
    ctx = ProblemContext(
        begin=begin, end=end, num_agents=num_agents, budget=budget, speeds=speeds
    )

    archive_solutions, front, log = _run_movns(rvalues, rpositions, ctx, config)
    archive_solutions.sort(key=lambda s: s.score[0])

    paths = [s.get_solution_paths() for s in front]
    scores = np.array([s.score for s in front])

    if scores.size > 0:
        print(f"Best reward score: {max(scores[:, 0]):.2f}")
    else:
        print("No solutions found in Pareto front")

    if config.save_results and paths:
        _save_results(paths, scores, log, map_name, max(speeds), config)

    if config.plot_results and paths:
        _plot_results(paths, scores, rpositions, rvalues, map_name, config)

    return paths


def _run_movns(rvalues, rpositions, ctx, config):
    np.random.seed(config.seed)
    random.seed(config.seed)

    archive = Archive(config)
    neighborhood = Neighborhood(config.algorithm)
    env = Map2D(rvalues=rvalues, rpositions=rpositions)
    evaluator = Evaluator(environment=env)
    runner = Runner(
        max_iterations=config.max_iterations,
        max_time=config.max_time,
        archive=archive,
        neighborhood=neighborhood,
        environment=env,
        evaluator=evaluator,
        problem_ctx=ctx,
    )

    log, elapsed_time = runner.run()
    print(f"Finished running in {elapsed_time:.2f} seconds.")

    # Re-evaluate front with exact RSSI (in case surrogate was used during search)
    evaluator.evaluate(archive.front)

    return archive.front + archive.dominated, archive.front, log


def _save_results(paths, scores, log, map_name, max_speed, config):
    results_dir = Path(config.out_dir) / map_name / str(max_speed)
    results_dir.mkdir(parents=True, exist_ok=True)

    for path, score in zip(paths, scores):
        with open(results_dir / "scores.pkl", "ab") as f:
            pickle.dump(score, f)
        with open(results_dir / "paths.pkl", "ab") as f:
            pickle.dump(path, f)
    with open(results_dir / "log.pkl", "ab") as f:
        pickle.dump(log, f)


def _plot_results(paths, scores, rpositions, rvalues, map_name, config):
    # Lazy import — viz is optional and heavy (matplotlib)
    from topcc.viz import plot_paths_with_rewards

    print("Plotting paths...")
    plots_dir = Path(config.img_dir) / "paths" / map_name
    plots_dir.mkdir(parents=True, exist_ok=True)
    existing_files = len([f for f in plots_dir.iterdir() if f.is_file()])

    for i, (path, score) in enumerate(zip(paths, scores)):
        filename = str(existing_files + i + 1)
        plot_paths_with_rewards(
            rpositions, rvalues, path, score,
            directory=str(plots_dir), fname=filename,
        )
