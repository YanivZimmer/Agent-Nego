import json
import logging
import sys
from typing import Dict, Any
from typing import cast

from geniusweb.actions.Accept import Accept
from geniusweb.actions.Action import Action
from geniusweb.actions.Offer import Offer
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
from geniusweb.issuevalue import DiscreteValue
from geniusweb.issuevalue import NumberValue
from geniusweb.profile.utilityspace.LinearAdditive import LinearAdditive

class StupidAgent(DefaultParty):
    """
    A Stupid party that places empty bids because it can't download the profile,
    and accepts the first incoming offer.
    """

    def __init__(self):
        super().__init__()
        self.getReporter().log(logging.INFO, "party is initialized")
        self._utilspace: LinearAdditive = None  # type:ignore
        self._profile = None
        self._lastReceivedBid: Bid = None

    # Override
    def notifyChange(self, info: Inform):
        # self.getReporter().log(logging.INFO,"received info:"+str(info))
        if isinstance(info, Settings):
            settings: Settings = cast(Settings, info)
            self._me = settings.getID()
            self._protocol = settings.getProtocol()
        elif isinstance(info, ActionDone):
            action: Action = cast(ActionDone, info).getAction()
            if isinstance(action, Offer):
                self._lastReceivedBid = cast(Offer, action).getBid()
        elif isinstance(info, YourTurn):
            # This is a stupid party
            if self._lastReceivedBid != None:
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
        if self._profile != None:
            self._profile.close()
            self._profile = None

    def valueToStr(v, p) -> str:
        v_str = ""
        if p.type == 0:
            v_str = str(DiscreteValue(v).getValue())
        else if p.type == 1:
            v_str = str(NumberValue(v).getValue())
        
        if v_str == "":
            self.getReporter().log(logging.WARNING, "Warning: Value wasn't found")
        return v_str

    def processAction(action):
        if isinstance(action, Offer):
            self._lastReceivedBid = Offer(action).getBid()
            # TODO: implement updateFreqMap
            # self.updateFreqMap(self._lastReceivedBid)
            utilVal = float(self._utilspace.getUtility(self._lastReceivedBid))
            # TODO: implement NegotiationData class
            # self.negotiationData.addBidUtil(utilVal)