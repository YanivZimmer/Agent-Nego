class NegotiationData:
    tSplit = 40

    def __init__(self):
        self.maxReceivedUtil = 0.0
        self.agreementUtil = 0.0
        self.opponentName = ''

        self.opponentUtil = 0.0
        self.opponentUtilByTime = [0.0] * NegotiationData.tSplit

    def addAgreementUtil(self, agreementUtil):
        self.agreementUtil = agreementUtil
        if agreementUtil > self.maxReceivedUtil:
            self.maxReceivedUtil = agreementUtil

    def addBidUtil(self, bidUtil):
        if bidUtil > self.maxReceivedUtil:
            self.maxReceivedUtil = bidUtil

    def updateOpponentOffers(self, opSum, opCounts):
        for i in range(NegotiationData.tSplit):
            self.opponentUtilByTime[i] = opSum[i] / opCounts[i] if opCounts[i] > 0 else 0.0

    def setOpponentName(self, opponentName):
        self.opponentName = opponentName

    def setOpponentUtil(self, oppUtil):
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