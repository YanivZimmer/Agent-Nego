import random

from agents.time_dependent_agent.time_dependent_agent import TimeDependentAgent
from tudelft_utilities_logging.Reporter import Reporter
#extra fields
import geniusweb.progress.Progress
import geniusweb.inform.Settings
from time import time
import geniusweb.issuevalue.Bid
class HardlinerAgent(TimeDependentAgent):
    """
    A simple party that places random bids and accepts when it receives an offer
    with sufficient utility.
    """
    progress1: geniusweb.progress.Progress.Progress

    def __init__(self, progress1, reporter: Reporter = None):
        super().__init__(reporter)
        #extra fields
        self.opCounter = None
        self.opSum = None
        self.t_phase = 0
        self.t_split = 0
        self.progress = progress1
        self.last_received_bid = geniusweb.issuevalue.Bid.Bid()
        self.best_offer_bid = geniusweb.issuevalue.Bid.Bid()
        self.optimal_bid = geniusweb.issuevalue.Bid.Bid()
        self.all_bids_list=[]
    # Override
    def getDescription(self) -> str:
        return (
            "Hardliner: does not concede. "
            + "Parameters minPower (default 1) and maxPower (default infinity) are used when voting"
        )

    # Override
    def getE(self) -> float:
        return 0.0

    def is_near_negotiation_end(self):
        #TODO make sure get is valid for progress
        return self.progress.get(int(time() * 1000)) > self.t_phase

    def calc_op_value(self,bid):
        pass
    def calc_utility(self,bid):
        #get utility from utility space
        #TODO implement
        return 1
    def is_good(self,bid):
        if bid==None:
            return False
        max_value = 0.95
        if self.optimal_bid != None:
            max_value = 0.95 * self.calc_utility(self.optimal_bid)

    def accept_bid(self):
        pass
    def _my_turn(self):
        #save average of the last avgSplit offers (only when frequency table is stabilized)
        if self.is_near_negotiation_end():
            index = int ((self.t_split - 1)/(1-self.t_phase) * (self.progress.get(int(time()*1000)) - self.t_phase))
            self.opSum[index] += self.calc_op_value(self.last_received_bid)
            self.opCounter[index] +=1
        if self.is_good(self.last_received_bid):
            #if the last bid is good- accept it.
            action = self.accept_bid()
        else:
            self._find_bid()

    def cmp_utility(self,first_bid,second_bid):
        #return 1 if first_bid with higher utility, 0 else
        return 1

    def is_op_good(self, bid):
        pass

    def on_negotiation_near_end(self):
        bid= geniusweb.issuevalue.Bid.Bid()
        for attempt in range(1000):
            if self.is_good(bid):
                return
            idx = random.randint(0,len(self.all_bids_list))
            bid = self.all_bids_list[idx]
        if not self.is_good(bid):
            bid=self.optimal_bid
        return bid
    def on_negotiation_continues(self):
        bid = geniusweb.issuevalue.Bid.Bid()
        for attempt in range(1000):
            if bid == self.optimal_bid or self.is_good(bid) or self.is_op_good(bid):
                break
            idx = random.randint(0, len(self.all_bids_list))
            bid = self.all_bids_list[idx]
            if self.progress.get(int(time() * 1000))>0.99 and self.is_good(self.best_offer_bid):
                bid = self.best_offer_bid
            if not self.is_good(bid):
               bid= self.optimal_bid
        return bid
    def _find_bid(self):
        bid=None
        if self.best_offer_bid == None:
            self.best_offer_bid = self.last_received_bid
        elif self.cmp_utility(self.last_received_bid,self.best_offer_bid):
            self.best_offer_bid = self.last_received_bid
            #bid= self.best_offer_bid
        if self.is_near_negotiation_end():
            bid = self.on_negotiation_near_end()
        else:
            bid = self.on_negotiation_continues()
        # action=Action(my_user,bid)
        #send action
