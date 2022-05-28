from geniusweb.issuevalue.Bid import Bid


class BidInfo:
    def __init__(self, bid: Bid, util=0.0):
        self._bid = bid
        self._util = util

    def set_util(self, util):
        self._util = util

    def get_bid(self):
        return self._bid

    def get_util(self):
        return self._util

    def __eq__(self, other):
        return self._bid.__eq__(other.get_bid())

    def __lt__(self, other):
        return self._util < other.get_util()
