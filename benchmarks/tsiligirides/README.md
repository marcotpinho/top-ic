# Tsiligirides OP set 2: acceleration-aware derivatives

Original archive and one extracted instance are copied from the [KU Leuven benchmark catalog](https://www.mech.kuleuven.be/en/mim/op), which cites Tsiligirides (1984). The archive contains 11 budget variants, each with 21 locations: start, end, and 19 tasks. Checksums and retrieval URL are in [provenance.json](provenance.json).

`single-30s.json` retains all task coordinates and rewards. Coordinates are interpreted as meters. Its 30-second flight budget, axis speed limits of 3 m/s, and axis acceleration limits of 1.5 m/s² are new experiment parameters, not a mathematically equivalent conversion of the original distance/travel budget. Initial and final velocities are zero. Original OP optimal rewards are consequently not reference optima for these experiments.

Recreate the derivative with `.venv/bin/python scripts/prepare_benchmark.py`. The source download contains no explicit license statement; attribution is preserved and no new license is asserted over original data.
