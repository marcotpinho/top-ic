import json
import matplotlib.image as image
from topcc.config import Config
from topcc.environment import smoke_problem
from topcc.solver import run_optimization,result_to_dict
from topcc.viz_icc import plot_fronts,plot_communication


def test_icc_plot_data_and_timeline(tmp_path):
    result=run_optimization(smoke_problem(2),Config(mode='team_kop_icc',max_evaluations=20,max_iterations=2,max_seconds=10))
    data=json.loads(json.dumps(result_to_dict(result)))
    plot_communication(data,tmp_path)
    plot_fronts({'Tc5':data['front']},tmp_path/'tc.png','Tc test')
    for path in ('full-communication.png','full-free-waypoints.png','full-pareto.png','full-paths-speed.png','tc.png'):
        pixels=image.imread(tmp_path/path)
        assert pixels.std()>.01 and pixels.shape[0]>100
