import json
from pathlib import Path
from topcc.viz import plot_result

def test_empty_front_plot(tmp_path):
    plot_result({'front':[]},tmp_path)
    assert (tmp_path/'pareto.png').stat().st_size>1000

def test_saved_trajectory_validation_and_plots(tmp_path):
    # Verify independent validator on committed experimental artifact, no optimizer run.
    import importlib.util
    root=Path(__file__).resolve().parents[1]
    result=root/'results/step2/epsilon-full.json'
    if not result.exists():
        import pytest
        pytest.skip("Campaign artifact unavailable")
    spec=importlib.util.spec_from_file_location('validate_saved',root/'scripts/validate_saved.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=json.loads(result.read_text());report=module.validate(data)
    assert report['solutions_checked']>0
    plot_result(data,tmp_path)
    assert all((tmp_path/name).stat().st_size>1000 for name in ('pareto.png','paths.png','speed.png'))

def test_independent_validator_rejects_corrupt_velocity():
    import importlib.util,copy,pytest
    root=Path(__file__).resolve().parents[1];result=root/'results/step2/epsilon-full.json'
    if not result.exists():pytest.skip('Campaign artifact unavailable')
    spec=importlib.util.spec_from_file_location('validate_saved',root/'scripts/validate_saved.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=json.loads(result.read_text());data=copy.deepcopy(data)
    data['front'][0]['trajectories'][0]['pieces'][0]['velocity'][0]=1000
    with pytest.raises(AssertionError):module.validate(data)
