import random
import numpy as np
import pickle
from pathlib import Path

import plot
from src.config import CONFIG
from src.entities.Archive import Archive
from src.entities.Evaluator import Evaluator
from src.entities.Runner import Runner
from src.entities.Map import Map
from src.entities.Neighborhood import Neighborhood
from src.entities.Solution import Solution


def run_optimization(
    rpositions: np.ndarray, # shape (n, 2)
    rvalues: np.ndarray, # shape (n,)
    budget: list[int],
    map_name: str,
    num_agents: int,
    speeds: list,
    begin: int = -1,
    end: int = -2
) -> list:
    Solution.set_parameters(begin, end, num_agents, budget, speeds)

    archive, front, log = run_movns(rvalues, rpositions)
    
    archive.sort(key=lambda solution: solution.score[0])

    paths = [solution.get_solution_paths() for solution in front]
    scores = np.array([solution.score for solution in front])

    if scores.size > 0:
        print(f"Best reward score: {max(scores[:, 0]):.2f}")
    else:
        print("No solutions found in Pareto front")

    if CONFIG.save_results and paths:
        save_results_to_files(paths, scores, log, map_name, max(speeds))

    if CONFIG.plot_results and paths:
        plot_solution_paths(paths, scores, rpositions, rvalues, map_name)

    return paths


def run_movns(
    rvalues: np.ndarray, # shape (n,)
    rpositions: np.ndarray, # shape (n, 2)
) -> tuple[list, list, list]:
    np.random.seed(CONFIG.seed)
    random.seed(CONFIG.seed)

    archive = Archive()
    neighborhood = Neighborhood(CONFIG.algorithm)
    mapp = Map(rvalues=rvalues, rpositions=rpositions, predict_distances=CONFIG.predict_distances)
    evaluator = Evaluator(map=mapp, predict_distances=CONFIG.predict_distances, should_save_to_db=CONFIG.save_to_db)
    runner = Runner(
        max_iterations=CONFIG.max_iterations,
        max_time=CONFIG.max_time,
        archive=archive,
        neighborhood=neighborhood,
        map=mapp,
        evaluator=evaluator
    )

    log, elapsed_time = runner.run()

    print(f"Finished running in {elapsed_time:.2f} seconds.")
    evaluator.predict_distances = False
    evaluator.evaluate(archive.front)

    return archive.front + archive.dominated, archive.front, log


def save_results_to_files(
    paths: list, 
    scores: np.ndarray, 
    log: list,
    map_name: str, 
    max_speed: float
) -> None:
    mode = "exact" if CONFIG.predict_distances == False else "surrogate"
    results_dir = f"{CONFIG.out_dir}/{map_name}/{max_speed}/{mode}"
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    for path, score in zip(paths, scores):
        with open(results_dir / "scores.pkl", "ab") as f:
            pickle.dump(score, f)
        with open(results_dir / "paths.pkl", "ab") as f:
            pickle.dump(path, f)

    with open(results_dir / "log.pkl", "ab") as f:
        pickle.dump(log, f)


def plot_solution_paths(
    paths: list,
    scores: np.ndarray,
    rpositions: np.ndarray, # shape (n, 2)
    rvalues: np.ndarray, # shape (n,)
    map_name: str,
) -> None:
    """
    Plot and save visualization of solution paths.
    
    Args:
        paths: List of solution paths
        scores: Array of solution scores
        rpositions: Positions of reward nodes
        rvalues: Reward values
        map_name: Name of the map
        output_dir: Output directory for plots
    """
    print("Plotting paths...")

    plots_dir = f"{CONFIG.img_dir}/paths/{map_name}"
    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    existing_files = len([f for f in plots_dir.iterdir() if f.is_file()])
    
    for i, (path, score) in enumerate(zip(paths, scores)):
        filename = str(existing_files + i + 1)
        plot.plot_paths_with_rewards(
            rpositions,
            rvalues,
            path,
            score,
            directory=str(plots_dir),
            fname=filename,
        )
