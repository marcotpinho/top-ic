"""RSSI (signal strength) models for communication quality evaluation."""

import numpy as np
from topcc.numba_kernels import calculate_rssi_kernel


class LogDistanceRSSI:
    """Free-space log-distance path loss model.

    RSSI = Pt - 10 * gamma * log10(d)

    This is the model used in the IROS 2025 paper.
    """

    def __init__(
        self,
        tx_power: float = -30.0,
        path_loss_exponent: float = 2.0,
    ):
        self.tx_power = tx_power
        self.path_loss_exponent = path_loss_exponent

    def compute(self, distance: float, noise: bool = False, noise_std: float = 1.0) -> float:
        rssi = calculate_rssi_kernel(distance, self.tx_power, self.path_loss_exponent)
        if noise:
            rssi += np.random.normal(0, noise_std)
        return rssi
