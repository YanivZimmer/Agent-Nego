from typing import List

class NegotiationData:
    tSplit: int = 40

    def __init__(self):
        self.maxReceivedUtil: float = 0.0
        self.agreementUtil: float = 0.0
        self.opponentName: str = ''

        self.opponentUtil: float = 0.0
        self.opponentUtilByTime:List[float] = [0.0] * NegotiationData.tSplit

    def addAgreementUtil(self, agreementUtil: float):
        self.agreementUtil = agreementUtil
        if agreementUtil > self.maxReceivedUtil:
            self.maxReceivedUtil = agreementUtil

    def addBidUtil(self, bidUtil: float):
        if bidUtil > self.maxReceivedUtil:
            self.maxReceivedUtil = bidUtil

    def updateOpponentOffers(self, opSum:List[float], opCounts: List[int]):
        for i in range(NegotiationData.tSplit):
            self.opponentUtilByTime[i] = opSum[i] / opCounts[i] if opCounts[i] > 0 else 0.0

    def setOpponentName(self, opponentName:str):
        self.opponentName = opponentName

    def setOpponentUtil(self, oppUtil: float):
        self.opponentUtil = oppUtil

    def getOpponentName(self):
        return self.opponentName

    def getMaxReceivedUtil(self):
        return self.maxReceivedUtil

    def getAgreementUtil(self):
        return self.agreementUtil

    def getOpponentUtil(self):
        return self.opponentUtil

    def getOpponentUtilByTime(self):
        return self.opponentUtilByTime
