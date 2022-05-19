from abc import ABC
from collections import defaultdict
from typing import List
from negotiation_data import NegotiationData
import math


class PersistentData(ABC):
    def __init__(self):
        self._t_split: int = 40
        self._t_phase: float = 0.2
        self._new_weight: float = 0.3
        self._smooth_width: float = 3
        self._opponent_decrease: float = 0.65
        self._default_alpha: float = 10.7

        self._avg_utility: float = 0.0
        self._negotiations: int = 0
        # dictionary ["string"] -> float
        self._avg_max_utility_opponent = defaultdict()
        # dictionary ["string"] -> int
        self._opponent_encounters = defaultdict()

        self._std_utility: float = 0.0
        self._nego_results: List[float] = []

        self._avg_opponent_utility = defaultdict()
        self._opponent_alpha = defaultdict()
        self._opponent_utility_by_time = defaultdict()

    def update(self, negotiation_data: NegotiationData):
        new_util = negotiation_data.getAgreementUtil() if negotiation_data.getAgreementUtil() else (
                self._avg_utility - 1.1 * math.pow(self._std_utility, 2))
        self._avg_utility = (self._avg_utility * self._negotiations + new_util) / (self._negotiations + 1)

        self._negotiations += 1

        self._nego_results.append(negotiation_data.getAgreementUtil())
        self._std_utility = 0.0

        for util in self._nego_results:
            self._std_utility += math.pow(util - self._avg_utility, 2)
        self._std_utility = math.sqrt(self._std_utility / self._negotiations)

        opponent = negotiation_data.getOpponentName()

        if opponent is not None:
            encounters = self._opponent_encounters.get(opponent) if opponent in self._opponent_encounters else 0
            self._opponent_encounters[opponent] = encounters + 1
            self._avg_utility = self._avg_max_utility_opponent.get(
                opponent) if opponent in self._avg_max_utility_opponent else 0.0
            self._avg_max_utility_opponent[opponent] = (
                    (self._avg_utility * encounters + negotiation_data.getMaxReceivedUtil()) / (encounters + 1))
            avg_op_util = self._avg_opponent_utility.get(opponent) if opponent in self._avg_opponent_utility else 0.0
            self._avg_opponent_utility[opponent] = (avg_op_util * encounters + negotiation_data.getOpponentUtil()) / (
                    encounters + 1)

            opponent_time_util: List[float] = []
            if opponent in self._opponent_utility_by_time:
                opponent_time_util = self._opponent_utility_by_time.get(opponent)
            else:
                opponent_time_util = [0.0] * self._t_split
            new_util_data: List[float] = negotiation_data.getOpponentUtilByTime()
            ratio = ((1 - self._new_weight) * opponent_time_util[0] + self._new_weight * new_util_data[0]) / \
                    opponent_time_util[0] if opponent_time_util[0] > 0.0 else 1

            for i in range(self._t_split):
                if new_util_data[i] > 0:
                    opponent_time_util[i] = (
                            (1 - self._new_weight) * opponent_time_util[i] + self._new_weight * new_util_data[i])
                else:
                    opponent_time_util[i] *= ratio
        self._opponent_utility_by_time[opponent] = opponent_time_util
        self._opponent_alpha[opponent] = self._calc_alpha(opponent)

    def _calc_alpha(opponent: str):
        pass
