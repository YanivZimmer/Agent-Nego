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
from geniusweb.actions.LearningDone import LearningDone
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
from geniusweb.progress.ProgressRounds import ProgressRounds

from agents.super_agent.utils.utils import get_ms_current_time
from agents.super_agent.utils.pair import Pair
from agents.super_agent.utils.persistent_data import PersistentData
from agents.super_agent.utils.negotiation_data import NegotiationData


class SuperAgent(DefaultParty):
    """
    A Super party that places empty bids because it can't download the profile,
    and accepts the first incoming offer.
    """

    def __init__(self):
        super().__init__()
        self.best_offer_bid: Bid = None
        # self.optimal_default_bid: Bid = None
        self.getReporter().log(logging.INFO, "party is initialized")
        self._profile = None
        self._profile_interface: ProfileInterface = None
        self._last_received_bid: Bid = None
        self._util_threshold = 0.95
        self._utility_space = None
        self._protocol = None
        # estimate opponent time-variant threshold function
        self.default_alpha = 10.7
        self.alpha = self.default_alpha
        self.t_split = 40
        self.t_phase = 0.4
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

        self._persistent_path: str = None
        self._persistent_data: PersistentData = None
        self._avg_utility = 0.9
        self._std_utility = 0.1
        self._all_bid_list: AllBidsList = None
        self._optimal_bid = None
        self._max_bid_space_iteration = 50000

        # NeogtiationData
        self._data_paths_raw: List[str] = []
        self._data_paths: List[str] = []
        self._negotiation_data: NegotiationData = None

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
                self._data_paths = []
                for data_path in self._data_paths_raw:
                    self._data_paths.append(FileLocation(uuid.UUID(data_path)).getFile())

            if "Learn" == self._protocol:
                # learning
                self.learn()
                val(self.getConnection()).send(LearningDone(self._me))
            else:
                # We are in the negotiation step.
                # Obtain all of the issues in the current negotiation domain

                self._negotiation_data = NegotiationData()
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
            # TODO: initalizie with negotiaiondata
            action: Action = cast(ActionDone, info).getAction()
            if self._me is not None and self._me != action.getActor():
                if self._opponent_name is None:
                    full_opponent_name = action.getActor().getName()
                    agent_index = full_opponent_name.rindex("_")
                    if agent_index != -1:
                        # which means index found
                        self._opponent_name = full_opponent_name[:agent_index]
                        self._negotiation_data.setOpponentName(self._opponent_name)
                        self.op_threshold = self._persistent_data.get_smooth_threshold_over_time(self._opponent_name
                                                                                                 )
                        if self.op_threshold is not None:
                            for i in range(1, self.t_split):
                                self.op_threshold[i] = self.op_threshold[i] if self.op_threshold[i] > 0 else \
                                    self.op_threshold[i - 1]
                        self.alpha = self._persistent_data.get_opponent_alpha(self._opponent_name)
                        self.alpha = self.alpha if self.alpha > 0.0 else self.default_alpha
                self.process_action(action)

        elif isinstance(info, YourTurn):
            # This is a super party
            if isinstance(self._progress, ProgressRounds):
                self._progress = self._progress.advance()
            action = self._my_turn()
            val(self.getConnection()).send(action)

        elif isinstance(info, Finished):
            self.terminate()
            # TODO:: handle NEGOTIATIONDATA
            finished_info = cast(Finished, info)
            agreements: Agreements = finished_info.getAgreements()
            self.process_agreements(agreements)
            if self._data_paths is not None and len(self._data_paths) != 0 and self._negotiation_data is not None:
                with open(self._data_paths[0]) as pers_file:
                    json.dump(self._negotiation_data, pers_file)

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
        if self._profile_interface is not None:
            self._profile_interface.close()
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

    def process_action(self, action: Action):
        if isinstance(action, Offer):
            self._last_received_bid = cast(Offer, action).getBid()
            self.update_freq_map(self._last_received_bid)
            util_value = float(self._utility_space.getUtility(self._last_received_bid))
            self._negotiation_data.addBidUtil(util_value)

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
        return self._utility_space.getUtility(bid)

    def is_good(self, bid, soft=1):
        if bid is None:
            return False
        max_value = 0.95 if self._optimal_bid is None else 0.95 * float(self.calc_utility(self._optimal_bid))
        avg_max_utility = self._persistent_data.get_avg_max_utility(self._opponent_name) \
            if self._persistent_data._known_opponent(self._opponent_name) \
            else self._avg_utility
        self._util_threshold = max_value - (
                max_value - 0.4 * avg_max_utility - 0.6 * self._avg_utility + self._std_utility ** 2) * \
                               (math.exp(self.alpha * self._progress.get(get_ms_current_time()) - 1) / math.exp(
                                   self.alpha) - 1)
        return float(self.calc_utility(bid)) >= soft*self._util_threshold

    def on_negotiation_near_end(self):
        bid: Bid = None
        best_bid: Bid = None
        soft = 0.8
        top_bids = {}
        best_bid_val=0
        top_val1 = 0
        top_val2 = 0
        top_val3 = 0
        for attempt in range(1000):
            #soft = soft-0.01*random.randint(-3 , 4)
            # if util > top_val1:
            #     top_bids[util]=bid
            #     top_val2=top_val1
            #     top_val1=util
            # elif util >top_val2:
            #     top_bids[]
            #
            if self.is_good(bid,soft):
                break
            idx = random.randint(0, self._all_bid_list.size())
            bid = self._all_bid_list.get(idx)
            util = self.calc_utility(bid)
            if util > best_bid_val:
                best_bid_val = util
                best_bid = bid
        # if not self.is_good(best_bid,0.7):
        #     bid = self._optimal_bid
        return best_bid

    def on_negotiation_continues(self):
        bid: Bid = None
        for attempt in range(1000):
            if bid == self._optimal_bid or self.is_good(bid) or self.is_op_good(bid):
                break
            idx = random.randint(0, self._all_bid_list.size())
            bid = self._all_bid_list.get(idx)
        if self._progress.get(get_ms_current_time()) > 0.99 and self.is_good(self.best_offer_bid):
            bid = self.best_offer_bid
        if not self.is_good(bid):
            bid = self._optimal_bid
        return bid

    def cmp_utility(self, first_bid, second_bid):
        # return 1 if first_bid with higher utility, 0 else
        return self._utility_space.getUtility(first_bid) > self._utility_space.getUtility(second_bid)

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

    def learn(self):
        for path in self._data_paths:
            try:
                with open(path) as f:
                    nego_data = json.load(f)
                    self._persistent_data.update(nego_data)
            except:
                raise Exception(f"Negotiation data path {0} does not exist".format(path))
        try:
            with open(self._persistent_path) as pers_file:
                json.dump(self._persistent_data, pers_file)
        except:
            raise Exception(f"Failed to write persistent data to path: {0}".format(self._persistent_path))

    def process_agreements(self, agreements: Agreements):
        # Check if we reached an agreement (walking away or passing the deadline
        # results in no agreement)
        if len(agreements.getMap().items()) > 0:
            # Get the bid that is agreed upon and add it's value to our negotiation data
            agreement: Bid = agreements.getMap().values().__iter__().__next__()
            self._negotiation_data.addAgreementUtil(float(self._utility_space.getUtility(agreement)))
            self._negotiation_data.setOpponentUtil(self.calc_op_value(agreement))

            self.getReporter().log(logging.INFO, "MY OWN THRESHOLD: {}".format(self._util_threshold))

            self.getReporter().log(logging.INFO, "MY OWN UTIL:{}".format(self._utility_space.getUtility(agreement)))
            self.getReporter().log(logging.INFO, "EXP OPPONENT UTIL:".format(self.calc_op_value(agreement)))
        else:
            self.getReporter().log(logging.INFO,
                                   "!!!!!!!!!!!!!! NO AGREEMENT !!!!!!!!!!!!!!! /// MY THRESHOLD: {}".format(
                                       self._util_threshold))

        self.getReporter().log(logging.INFO, "TIME OF AGREEMENT: {}".format(self._progress.get(get_ms_current_time())))
        # update the opponent offers map, regardless of achieving agreement or not
        try:
            self._negotiation_data.updateOpponentOffers(self.op_sum, self.op_counter)
        except Exception as e:
            pass
