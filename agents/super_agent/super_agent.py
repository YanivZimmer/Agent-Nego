import json
import logging
import math
import os.path
import random
import sys
import json
import uuid
from typing import Dict, Any
from time import time
from typing import cast
from collections import defaultdict
from typing import List
from geniusweb.actions.ActionWithBid import ActionWithBid
from geniusweb.profileconnection.ProfileInterface import ProfileInterface
from geniusweb.actions.Accept import Accept
from geniusweb.actions.Action import Action
from geniusweb.actions.Offer import Offer
from geniusweb.actions.FileLocation import FileLocation
from geniusweb.issuevalue.Domain import Domain
from geniusweb.actions.PartyId import PartyId
from geniusweb.inform.ActionDone import ActionDone
from geniusweb.inform.Finished import Finished
from geniusweb.inform.Inform import Inform
from geniusweb.inform.Settings import Settings
from geniusweb.inform.YourTurn import YourTurn
from geniusweb.issuevalue.Bid import Bid
from geniusweb.bidspace.AllBidsList import AllBidsList
from geniusweb.party.Capabilities import Capabilities
from geniusweb.party.DefaultParty import DefaultParty
from geniusweb.utils import val
from geniusweb.issuevalue.Value import Value
from geniusweb.issuevalue import DiscreteValue
from geniusweb.issuevalue import NumberValue
from geniusweb.profile.utilityspace.LinearAdditive import LinearAdditive
from geniusweb.inform.Agreements import Agreements
from geniusweb.profile.utilityspace.UtilitySpace import UtilitySpace
from geniusweb.profileconnection.ProfileConnectionFactory import (
    ProfileConnectionFactory,
)

from agents.super_agent.utils.utils import get_ms_current_time
from agents.super_agent.utils.pair import Pair
from agents.super_agent.utils.persistent_data import PersistentData


class SuperAgent(DefaultParty):
    """
    A Super party that places empty bids because it can't download the profile,
    and accepts the first incoming offer.
    """

    def __init__(self):
        super().__init__()
        self.t_split = None
        self.best_offer_bid: Bid = None
        self.optimal_default_bid: Bid = None
        self.getReporter().log(logging.INFO, "party is initialized")
        self._profile = None
        self._profile_interface: ProfileInterface = None
        self._last_received_bid: Bid = None
        self.util_threshold = 0.95
        self._utility_space = None
        self._protocol = None
        # estimate opponent time-variant threshold function
        self.default_alpha = 10.7
        self.alpha = self.default_alpha
        self.t_split = 40
        self.t_phase = 0.2
        self.op_counter = [0] * self.t_split
        self.op_sum = [0.0] * self.t_split
        self.op_threshold = [0.0] * self.t_split
        # game details
        self._me = None
        self._opponent_name = None

        # (issue,value,typeof(value) -> frequency
        self._freq_map = defaultdict()
        self._domain = None
        self._profile = None
        self._progress = None

        self._persistent_path: uuid.UUID = None
        self._persistent_data: PersistentData = None
        self._avg_utility = 0.9
        self._std_utility = 0.1

        self._all_bid_list: AllBidsList = None
        self._optimal_bid = None
        self._max_bid_space_iteration = 50000

        # NeogtiationData
        self._data_paths_raw: List[str] = []
        self.data_paths: List[str] = []

    # Override
    def notifyChange(self, info: Inform):
        # self.getReporter().log(logging.INFO,"received info:"+str(info))
        if isinstance(info, Settings):
            settings: Settings = cast(Settings, info)
            self._me = settings.getID()
            self._progress = settings.getProgress()
            self._protocol = settings.getProtocol().getURI().getPath()
            self._parameters = settings.getParameters()
            if "persistentstate" in self._parameters.getParameters():
                # TODO: fix persistent path initialization
                persistent_state_path = self._parameters.get('persistentstate')
                if isinstance(persistent_state_path, str):
                    persistent_state_path_str = cast(str, persistent_state_path)
                    path_persistent_state_uuid = uuid.UUID(persistent_state_path_str)
                    self._persistent_path = FileLocation(path_persistent_state_uuid).getFile()
                else:
                    print("persistent_state in not string")
                # print("persistent_space:{}".format(self._persistent_path))

            if self._persistent_path is not None and os.path.exists(self._persistent_path):
                # json load
                self._persistent_data: PersistentData = json.loads(self._persistent_path)
                self._avg_utility = self._persistent_data.avg_utility
                self._std_utility = self._persistent_data.std_utility
                print("avg: " + self._avg_utility + "  std: " + self._std_utility * self._std_utility)
            else:
                self._persistent_data = PersistentData()
            # TODO: add negotiondata
            if "negotiationdata" in self._parameters.getParameters():
                self._data_paths_raw = self._parameters.get("negotiationdata")
                self.data_paths = []
                for data_path in self._data_paths_raw:
                    self.data_paths.append(FileLocation(uuid.UUID(data_path)).getFile())

            if "Learn" == self._protocol:
                # learning
                # TODO: fill the learning stuff here
                pass
            else:
                # We are in the negotiation step.
                # TODO: fill the other stuff here
                # Obtain all of the issues in the current negotiation domain

                # TODO: initialize negotiationdata
                self._profile_interface = ProfileConnectionFactory.create(
                    info.getProfile().getURI(), self.getReporter()
                )
                self._profile = self._profile_interface.getProfile()
                self._domain = self._profile.getDomain()

                if self._freq_map is None:
                    self._freq_map = defaultdict()
                else:
                    self._freq_map.clear()

                issues = self._domain.getIssues()
                for issue in issues:
                    p = Pair()
                    vs = self._domain.getValues(issue)
                    if isinstance(vs.get(0), DiscreteValue.DiscreteValue):
                        p.value_type = 0
                    elif isinstance(vs.get(0), NumberValue.NumberValue):
                        p.value_type = 1
                    for v in vs:
                        vstr = self.value_to_str(v, p)
                        p.vlist[vstr] = 0
                    self._freq_map[issue] = p

                self._utility_space = self._profile
                self._all_bid_list: AllBidsList = AllBidsList(domain=self._domain)
                r = self._max_bid_space_iteration > self._all_bid_list.size()
                if r is True:
                    mx_util = 0
                    bid_space_size = self._all_bid_list.size()
                    for i in range(bid_space_size):
                        bid = self._all_bid_list.get(i)
                        candidate = self._utility_space.getUtility(bid=bid)
                        if candidate > mx_util:
                            mx_util = candidate
                            self._optimal_bid = bid
                else:
                    mx_util = 0
                    bid_space_size = self._all_bid_list.size()
                    for attempt in range(self._max_bid_space_iteration):
                        i = random.randint(0, bid_space_size)
                        bid = self._all_bid_list.get(i)
                        candidate = self._utility_space.getUtility(bid=bid)
                        if candidate > mx_util:
                            mx_util = candidate
                            self._optimal_bid = bid




        elif isinstance(info, ActionDone):
            action: Action = cast(ActionDone, info).getAction()
            if self._me is not None and self._me != action.getActor():
                if self._opponent_name is None:
                    full_opponent_name = action.getActor().getName()
                    agent_index = full_opponent_name.rindex("_")
                    if agent_index != -1:
                        # which means index found
                        self._opponent_name = full_opponent_name[:agent_index]
                self.processAction(action)

                # self.negotiation_data.setOpponentName(self._opponent_name)
                # self.opThreshold = self.persistentState.getSmoothThresholdOverTime(self._opponentName);
                # if self.opThreshold is not None:
                #     for i in range(1, self.t_split):
                #         self.opThreshold[i] = self.opThreshold[i] if self.opThreshold[i] > 0 else \
                #             self.opThreshold[i - 1]
                # self.alpha = self.persistentState.getOpponentAlpha(self._opponent_name)
                # self.alpha = self.alpha if self.alpha > 0.0 else self.defualtAlpha
        elif isinstance(info, YourTurn):
            # This is a super party
            if self._last_received_bid is not None:
                self.getReporter().log(logging.INFO, "sending accept:")
                action = self._my_turn()
                # accept = Accept(self._me, self._last_received_bid)
                val(self.getConnection()).send(action)
            else:
                # We have no clue about our profile
                offer: Offer = Offer(self._me, Bid({}))
                self.getReporter().log(logging.INFO, "sending empty offer:")
                val(self.getConnection()).send(offer)
                self.getReporter().log(logging.INFO, "sent empty offer:")
        elif isinstance(info, Finished):
            self.terminate()
        else:
            self.getReporter().log(
                logging.WARNING, "Ignoring unknown info " + str(info)
            )

    # Override
    def getCapabilities(self) -> Capabilities:
        return Capabilities(
            set(["SAOP", "Learn"]), set(["geniusweb.profile.utilityspace.LinearAdditive"])
        )

    # Override
    def getDescription(self) -> str:
        return "This is a party of ANL 2022. It can handle the Learn protocol and learns simple characteristics of the opponent."

    # Override
    def terminate(self):
        self.getReporter().log(logging.INFO, "party is terminating:")
        super().terminate()
        # TODO:  fix profile shit
        # if self._profile != None:
        #     self._profile.close()
        #     self._profile = None

    def value_to_str(self, v: Value, p: Pair) -> str:
        v_str = ""
        if p.value_type == 0:
            v_str = str(cast(DiscreteValue, v).getValue())
        elif p.value_type == 1:
            v_str = str(cast(NumberValue, v).getValue())

        if v_str == "":
            self.getReporter().log(logging.WARNING, "Warning: Value wasn't found")
        return v_str

    def processAction(self, action: Action):
        if isinstance(action, Offer):
            self._last_received_bid = cast(Offer, action).getBid()
            # TODO: implement updateFreqMap

            self.update_freq_map(self._last_received_bid)

            # self.updateFreqMap(self._last_received_bid)

            # utilVal = float(self._utilspace.getUtility(self._last_received_bid))

            # TODO: implement NegotiationData class
            # self.negotiationData.addBidUtil(utilVal)

    def update_freq_map(self, bid: Bid):
        if bid is not None:
            issues = bid.getIssues()
            for issue in issues:
                p: Pair = self._freq_map[issue]
                v: Value = bid.getValue(issue)
                vs: str = self.value_to_str(v, p)
                p.vlist[vs] = p.vlist[vs] + 1

    def calc_op_value(self, bid: Bid):
        value: float = 0
        issues: set[str] = bid.getIssues()
        val_util: list[float] = [0] * len(issues)
        is_weight: list[float] = [0] * len(issues)
        k: int = 0
        for issue in issues:
            p: Pair = self._freq_map[issue]
            v: Value = bid.getValue(issue)
            vs: str = self.value_to_str(v=v, p=p)
            sum_of_values = 0
            max_value = 1
            for vString in p.vlist.keys():
                sum_of_values = sum_of_values + p.vlist.get(vString)
                max_value = max(max_value, p.vlist.get(vString))
            val_util[k] = p.vlist.get(vs) / max_value
            mean = sum_of_values / len(p.vlist)
            for v_string in p.vlist.keys():
                is_weight[k] = is_weight[k] + math.pow(p.vlist.get(v_string) - mean, 2)
            is_weight[k] = 1 / math.sqrt((is_weight[k] + 0.1) / len(p.vlist))
            k = k + 1
        sum_of_weight = 0
        for k in range(len(issues)):
            value = value + val_util[k] * is_weight[k]
            sum_of_weight = sum_of_weight + is_weight[k]
        return value / sum_of_weight

    def is_op_good(self, bid: Bid):
        if bid is None:
            return False
        value = self.calc_op_value(bid=bid)
        index = int(
            ((self.t_split - 1) / (1 - self.t_phase) * (self._progress.get(get_ms_current_time()) - self.t_phase)))
        op_threshold = max(1 - 2 * self.op_threshold[index], 0.2) if self.op_threshold is not None else 0.6
        return value > op_threshold
        # index = (int)((t_split - 1) / (1 - t_phase) * (progress.get(System.currentTimeMillis()) - t_phase));

    def is_near_negotiation_end(self):
        return self._progress.get(get_ms_current_time()) > self.t_phase

    def calc_utility(self, bid):
        # get utility from utility space
        # TODO implement
        return 1

    def is_good(self, bid):
        if bid == None:
            return False
        max_value = 0.95
        if self.optimal_default_bid != None:
            max_value = 0.95 * self.calc_utility(self.optimal_default_bid)

    def on_negotiation_near_end(self):
        bid: Bid = None
        for attempt in range(1000):
            if self.is_good(bid):
                return bid
            idx = random.randint(0, self._all_bid_list.size())
            bid = self._all_bid_list.get(idx)
        if not self.is_good(bid):
            bid = self.optimal_default_bid
        return bid

    def on_negotiation_continues(self):
        bid: Bid = None
        for attempt in range(1000):
            if bid == self._optimal_bid or self.is_good(bid) or self.is_op_good(bid):
                break
            idx = random.randint(0, self._all_bid_list.size())
            bid = self._all_bid_list.get(idx)
        if self._progress.get(int(time() * 1000)) > 0.99 and self.is_good(self.best_offer_bid):
            bid = self.best_offer_bid
        if not self.is_good(bid):
            bid = self._optimal_bid
        return bid

    def cmp_utility(self, first_bid, second_bid):
        # return 1 if first_bid with higher utility, 0 else
        return 1

    def _find_bid(self):
        bid: Bid = None
        if self.best_offer_bid is None:
            self.best_offer_bid = self._last_received_bid
        elif self.cmp_utility(self._last_received_bid, self.best_offer_bid):
            self.best_offer_bid = self._last_received_bid
            # bid= self.best_offer_bid
        if self.is_near_negotiation_end():
            bid = self.on_negotiation_near_end()
        else:
            bid = self.on_negotiation_continues()
        # action=Action(my_user,bid)

        action: Offer = Offer(self._me, bid)
        return action

    def _my_turn(self):
        # save average of the last avgSplit offers (only when frequency table is stabilized)
        if self.is_near_negotiation_end():
            index = int(
                (self.t_split - 1) / (1 - self.t_phase) * (self._progress.get(get_ms_current_time()) - self.t_phase))
            self.op_sum[index] += self.calc_op_value(self._last_received_bid)
            self.op_counter[index] += 1
        if self.is_good(self._last_received_bid):
            # if the last bid is good- accept it.
            action = Accept(self._me, self._last_received_bid)
        else:
            action = self._find_bid()
        return action
