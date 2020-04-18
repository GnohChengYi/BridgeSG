# handles everything in a bridge game

class Game:
    '''Models a bridge game.
    
    players: list of Player objects (Player implemented as dict)
    # TODO to complete
        player{'id', 'name', 'hand', 'partnerId', ...}
        id>0: human;  id<0: AI
    bid (str): current highest bid, in '2S' (2 spades) format
    phase: 0=waiting, 1=bidding, 2=playing
    AIindices: available indices for AI, use the first element as current index'''
    
    
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

    def start(self):
        self.phase = 1
        # deal cards
