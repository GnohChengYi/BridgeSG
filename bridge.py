# handles everything in a bridge game
import random


class Game:
    '''Models a bridge game.
    
    players: list of Player objects (Player implemented as dict)
    # TODO to complete
        player{'id', 'name', 'hand', 'partnerId', ...}
        id>0: human;  id<0: AI
    bid (str): current highest bid, in '2S' (2 spades) format
    phase: 0=waiting, 1=bidding, 2=playing
    AIindices: available indices for AI, use the first element as current index
    '''
    
    def __init__(self):
        self.players = []
        self.bid = ''
        # TODO change phase specifications in comments as necessary
        self.phase = 0
        self.AIindices = [1, 2, 3, 4]
    
    def addHuman(self, id, name):
        '''Returns True if successfully added human player, False otw.'''
        # check if player already in game
        for player in self.players:
            if player['id'] == id:
                return False
        # should be less than 4 players, otw all btns removed -> won't reach here
        self.players.append({'id':id, 'name':name})
        return True

    def delHuman(self, id, name):
        '''Returns True if successfully deleted human player, False otw.'''
        # check if player in game
        for player in self.players:
            if player['id'] == id:
                self.players.remove(player)
                return True
        return False
    
    def addAI(self):
        # should be less than 4 players, otw all btns removed -> won't reach here
        self.players.append(
            {'id':-self.AIindices[0], 'name':'AI '+str(self.AIindices[0])}
        )
        self.AIindices = self.AIindices[1:] + self.AIindices[:1]

    def delAI(self):
        '''Returns True if successfully deleted AI, False otw.'''
        # check if player in game
        for player in self.players:
            if player['id'] < 0:
                self.players.remove(player)
                return True
        return False
    
    def full(self):
        '''Returns True if full of players (4), False otw.'''
        return len(self.players) >= 4
    
    def started(self):
        '''Returns True if game started, False otw.'''
        return self.phase > 0

    def dealCards():
        '''Returns (hand1, hand2, hand3, hand4).
        
        handN = [card1, card2, card3, ..., ]
        cardN = 'SA'(SpadeAce) | 'HQ'(HeartQueen) | 'DT'(DiamondTen) | 'C8' (Club8)
        '''
        # hard code so that don't need generate everytime (performance purpose)
        deck = ['SA','SK','SQ','SJ','ST','S9','S8','S7','S6','S5','S4','S3','S2',
                'HA','HK','HQ','HJ','HT','H9','H8','H7','H6','H5','H4','H3','H2',
                'DA','DK','DQ','DJ','DT','D9','D8','D7','D6','D5','D4','D3','D2',
                'CA','CK','CQ','CJ','CT','C9','C8','C7','C6','C5','C4','C3','C2']
        random.shuffle(deck)
        return (deck[:13], deck[13:26], deck[26:39], deck[39:])
        
    def start(self):
        '''Deals cards.'''
        self.phase = 1
        def dealCards():
            '''Returns (hand1, hand2, hand3, hand4).
            
            handN = [card1, card2, card3, ..., ]
            cardN = 'SA'(SpadeAce) | 'HQ'(HeartQueen) | 
                    'DT'(DiamondTen) | 'C8' (Club8)
            '''
            # hard code so that don't need generate everytime (performance purpose)
            deck = [
                'SA','SK','SQ','SJ','ST','S9','S8','S7','S6','S5','S4','S3','S2',
                'HA','HK','HQ','HJ','HT','H9','H8','H7','H6','H5','H4','H3','H2',
                'DA','DK','DQ','DJ','DT','D9','D8','D7','D6','D5','D4','D3','D2',
                'CA','CK','CQ','CJ','CT','C9','C8','C7','C6','C5','C4','C3','C2'
            ]
            random.shuffle(deck)
            return (deck[:13], deck[13:26], deck[26:39], deck[39:])
        hands = dealCards()
        for i in range(4):
            self.players[i]['hand'] = hands[i]
