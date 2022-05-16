from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import cast, List
import unittest

from geniusweb.actions.Accept import Accept
from geniusweb.actions.Action import Action
from geniusweb.actions.Offer import Offer
from geniusweb.actions.PartyId import PartyId
from geniusweb.actions.Votes import Votes
from geniusweb.bidspace.AllBidsList import AllBidsList
from geniusweb.connection.ConnectionEnd import ConnectionEnd
from geniusweb.inform.ActionDone import ActionDone
from geniusweb.inform.Inform import Inform
from geniusweb.inform.Settings import Settings
from geniusweb.inform.Voting import Voting
from geniusweb.inform.YourTurn import YourTurn
from geniusweb.issuevalue.Bid import Bid
from geniusweb.issuevalue.NumberValue import NumberValue
from geniusweb.profile.Profile import Profile
from geniusweb.profile.utilityspace.LinearAdditive import LinearAdditive
from geniusweb.profile.utilityspace.UtilitySpace import UtilitySpace
from geniusweb.progress.ProgressTime import ProgressTime
from geniusweb.references.Parameters import Parameters
from geniusweb.references.ProfileRef import ProfileRef
from geniusweb.references.ProtocolRef import ProtocolRef
from geniusweb.references.Reference import Reference
from pyson.ObjectMapper import ObjectMapper
from tudelft.utilities.listener.DefaultListenable import DefaultListenable
from uri.uri import URI  # type: ignore 

from randomparty.RandomParty import RandomParty


class MyConn(ConnectionEnd[Inform, Action], DefaultListenable):
    def __init__(self):
        super().__init__()
        self._actions:List[Action]=[]
    
    def send(self,data:Action ):
        self._actions.append(data)
        
    def getReference(self) -> Reference:
        return cast(Reference,None)

    def getRemoteURI(self)->URI: 
        return URI("whatever")
    
    def close(self):
        pass

    def getError(self) -> Exception:
        return cast(Exception, None)
    
    def getActions(self)-> List[Action]:
        return self._actions
    
class RandomPartyTest(unittest.TestCase):
    pyson = ObjectMapper()
    
    PARTY1 = PartyId("party1")
    profileref = ProfileRef(URI("file:test/resources/japantrip1.json"))
    PROFILE = ProfileRef(URI("file:test/resources/testprofile.json"))
    protocolref = ProtocolRef(URI("SAOP"))
    mopacProtocol = ProtocolRef(URI("MOPAC"));
    progress=ProgressTime(1000, datetime.fromtimestamp(12345))
    parameters=Parameters()
    mopacSettings = Settings(PARTY1,  PROFILE, mopacProtocol,progress, parameters)
    serialized =  Path("test/resources/testprofile.json").read_text("utf-8")
    profile:UtilitySpace = pyson.parse(json.loads(serialized), LinearAdditive) #type:ignore     

    def setUp(self):
        self.party=RandomParty()
        self.connection = MyConn()
        # we load the profile here too, to find a good bid
    

    def test_smoke(self):
        RandomParty()
        
    def testConnect(self):
        party=RandomParty()
        party.connect(self.connection)
        party.disconnect()
        
        
    def testSendInfo(self):
        settings  = Settings(self.PARTY1, self.profileref, self.protocolref, self.progress, self.parameters )
        
        self.party.connect(self.connection)
        self.connection.notifyListeners(settings)
        self.party.disconnect()
        self.assertEquals([], self.connection.getActions())
        
    def testSendYourTurn(self):
        self.assertEqual(0, len(self.connection.getActions()))
        settings  = Settings(self.PARTY1, self.profileref, self.protocolref, self.progress, self.parameters )

        self.party.connect(self.connection)
        self.connection.notifyListeners(settings)
        self.connection.notifyListeners(YourTurn())
        self.party.disconnect()
        
        actions = self.connection.getActions()
        self.assertEquals(1, len(actions))
        self.assertTrue(isinstance(actions[0], Offer))
        print("party did an offer: "+repr(actions[0]))

    def testSendOfferAndYourTurn(self):
        settings  = Settings(self.PARTY1, self.profileref, self.protocolref, self.progress, self.parameters )

        # nonsense bid, party should not accept
        bid=Bid({'a':NumberValue(Decimal(1))})
        offer = Offer(PartyId('other'), bid)

        self.party.connect(self.connection)
        self.connection.notifyListeners(settings)
        self.connection.notifyListeners(ActionDone(offer))
        self.connection.notifyListeners(YourTurn())
        self.party.disconnect()
        
        actions = self.connection.getActions()
        self.assertEquals(1, len(actions))
        self.assertTrue(isinstance(actions[0], Offer))


    def testVoting(self) :
        self.assertEqual(0, len(self.connection.getActions()))
        self.party.connect(self.connection);
        self.party.notifyChange(self.mopacSettings);

        bid = self._findGoodBid()
        offer = Offer(self.PARTY1, bid)
        self.party.notifyChange(Voting([offer],{self.PARTY1: 1}))
        self.assertEqual(1, len(self.connection.getActions()))
        action = self.connection.getActions()[0]
        self.assertTrue(isinstance(action,Votes))
        self.assertEqual(1, len(action.getVotes()))
        self.assertEqual(bid, next(iter(action.getVotes())).getBid())
        
    def _findGoodBid(self)-> Bid:
        for bid in AllBidsList(self.profile.getDomain()):
            if self.profile.getUtility(bid) > 0.7:
                     return bid;
        raise ValueError("Test can not be done: there is no good bid with utility>0.7");
