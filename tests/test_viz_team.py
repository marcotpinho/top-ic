import matplotlib.image as image
from topcc.environment import smoke_problem
from topcc.config import Config
from topcc.solver import result_to_dict,run_optimization
from topcc.viz_team import plot_result,plot_comparison

def test_team_plots(tmp_path):
    data=result_to_dict(run_optimization(smoke_problem(2),Config(mode='team_kop',max_evaluations=1)))
    representative=plot_result(data,tmp_path);plot_comparison({'full':data},tmp_path/'comparison.png')
    assert len(representative['trajectories'])==2
    for name in ('full-pareto.png','full-paths-speed.png','comparison.png'):
        pixels=image.imread(tmp_path/name)
        assert pixels.shape[0]>100 and pixels.std()>.01


def test_stationary_team_plot(tmp_path):
    from topcc.config import Problem,MotionLimits
    p=Problem((),(0,0),(0,0),(10,10),(MotionLimits(),)*2,((0,0),)*2)
    data=result_to_dict(run_optimization(p,Config(mode='team_kop',max_evaluations=1)))
    assert plot_result(data,tmp_path)['completion_times']==(0.,0.)
