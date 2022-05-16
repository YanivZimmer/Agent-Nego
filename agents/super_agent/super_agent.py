import json
import logging
import math
import sys
from typing import Dict, Any
from time import time
from typing import cast
from collections import defaultdict
from geniusweb.actions.ActionWithBid import ActionWithBid
from geniusweb.actions.Accept import Accept
from geniusweb.actions.Action import Action
from geniusweb.actions.Offer import Offer
from geniusweb.issuevalue.Domain import Domain
from geniusweb.actions.PartyId import PartyId
from geniusweb.inform.ActionDone import ActionDone
from geniusweb.inform.Finished import Finished
from geniusweb.inform.Inform import Inform
from geniusweb.inform.Settings import Settings
from geniusweb.inform.YourTurn import YourTurn
from geniusweb.issuevalue.Bid import Bid
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
from agents.super_agent.utils.negotiation_data import NegotiationData


class SuperAgent(DefaultParty):
    """
    A Super party that places empty bids because it can't download the profile,
    and accepts the first incoming offer.
    """

    def __init__(self):
        super().__init__()
        self.getReporter().log(logging.INFO, "party is initialized")
        self._utilspace: LinearAdditive = None  # type:ignore
        self._profile = None
        self._lastReceivedBid: Bid = None
        self.utilThreshold = 0.95
        self.utilitySpace = None
        self._protocol = None
        # estimate opponent time-variant threshold function
        self.defualtAlpha = 10.7
        self.alpha = self.defualtAlpha
        self.tSplit = 40
        self.tPhase = 0.2
        self.opCounter = [0] * self.tSplit
        self.opSum = [0.0] * self.tSplit
        self.opThreshold = [0.0] * self.tSplit
        # game details
        self._me = None
        self._opponent_name = None

        # (issue,value,typeof(value) -> frequency
        self._freq_map = defaultdict()
        self._domain = None
        self._profile = None
        self._progress = None

        self._negotiationData = None

    # Override
    def notifyChange(self, info: Inform):
        # self.getReporter().log(logging.INFO,"received info:"+str(info))
        if isinstance(info, Settings):
            settings: Settings = cast(Settings, info)
            self._me = settings.getID()
            self._progress = settings.getProgress()
            self._protocol = settings.getProtocol()
            profile_connection = ProfileConnectionFactory.create(
                info.getProfile().getURI(), self.getReporter()
            )
            self._profile = profile_connection.getProfile()
            self._domain = self._profile.getDomain()

            if "Learn" == self._protocol:
                # learning
                # TODO: fill the learning stuff here
                pass
            else:
                self._negotiationData = NegotiationData()
                # We are in the negotiation step.
                # TODO: fill the other stuff here
                # Obtain all of the issues in the current negotiation domain
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
                #     for i in range(1, self.tSplit):
                #         self.opThreshold[i] = self.opThreshold[i] if self.opThreshold[i] > 0 else \
                #             self.opThreshold[i - 1]
                # self.alpha = self.persistentState.getOpponentAlpha(self._opponent_name)
                # self.alpha = self.alpha if self.alpha > 0.0 else self.defualtAlpha
        elif isinstance(info, YourTurn):
            # This is a super party
            if self._lastReceivedBid is not None:
                self.getReporter().log(logging.INFO, "sending accept:")
                accept = Accept(self._me, self._lastReceivedBid)
                val(self.getConnection()).send(accept)
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
            self._lastReceivedBid = Offer(action).getBid()
            self.update_freq_map(self._lastReceivedBid)
            utilVal = float(self._utilspace.getUtility(self._lastReceivedBid))
            self._negotiationData.addBidUtil(utilVal)

    def processAgreements(self, agreements: Agreements) :
        # Check if we reached an agreement (walking away or passing the deadline
        # results in no agreement)
        if len(agreements.getMap().items()) > 0:
            # Get the bid that is agreed upon and add it's value to our negotiation data
            agreement = agreements.getMap().values().__iter__().__next__()
            self.negotiationData.addAgreementUtil(self.utilitySpace.getUtility(agreement).doubleValue())
            self.negotiationData.setOpponentUtil(self.calc_op_value(agreement))
            
            self.getReporter().log(logging.INFO, "MY OWN THRESHOLD: " + self.utilThreshold)
            
            self.getReporter().log(logging.INFO, "MY OWN UTIL: " + float(self.utilitySpace.getUtility(agreement)))
            self.getReporter().log(logging.INFO, "EXP OPPONENT UTIL: " + self.calcOpValue(agreement))
        else:
            self.getReporter().log(logging.INFO, "!!!!!!!!!!!!!! NO AGREEMENT !!!!!!!!!!!!!!! /// MY THRESHOLD: " + self.utilThreshold)

        self.getReporter().log(logging.INFO, "TIME OF AGREEMENT: " + self._progress.get(get_ms_current_time()))
        # update the opponent offers map, regardless of achieving agreement or not
        try:
            self._negotiationData.updateOpponentOffers(self.opSum, self.opCounter)
        except Exception as e:
            pass

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
        index = ((self.tSplit - 1) / (1 - self.tPhase) * (self._progress.get(get_ms_current_time()) - self.tPhase))
        op_threshold = max(1 - 2 * self.opThreshold[index], 0.2) if self.opThreshold is not None else 0.6
        return value > op_threshold
        # index = (int)((tSplit - 1) / (1 - tPhase) * (progress.get(System.currentTimeMillis()) - tPhase));
