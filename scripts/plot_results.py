"""Regenerate figures from saved outputs without running optimization."""
import argparse
from topcc.viz import plot_result
parser=argparse.ArgumentParser()
parser.add_argument('result');parser.add_argument('output_dir')
args=parser.parse_args();plot_result(args.result,args.output_dir)
