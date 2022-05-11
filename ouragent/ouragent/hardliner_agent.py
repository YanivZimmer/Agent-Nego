
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
        self.last_recieved_bid = geniusweb.issuevalue.Bid.Bid()
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

    def _my_turn(self):
        #save average of the last avgSplit offers (only when frequency table is stabilized)
		if (self.is_near_negotiation_end()):
		    index = int ((self.t_split - 1)/(1-self.t_phase) * (self.progress.get(int(time()*1000)) - self.t_phase))
		    self.opSum[index] += self.calc_op_value(self.last_recieved_bid)
		    self.opCounter[index] +=1

