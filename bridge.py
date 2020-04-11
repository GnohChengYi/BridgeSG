# handles everything in a bridge game


class Player:
    '''Models a player.
    
    id: user_id (>0) for human, negative integer for AI
    hand: list of cards
        card: str with 2 char, e.g. 'SK' means King of Spades
    partner: another Player object
    setCount: number of winned sets
    '''
    
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.hand = []
        self.partner = None
        self.setCount = 0
    
    def __str__(self):
        result = str(self.id) + str(self.name) + str(self.hand)
        result += str(self.partner.name) + str(self.setCount)
        return result


class AI(Player):
    '''Models an AI player. Subclass of Player.'''
    index = 0
    
    def __init__(self):
        id = index
        name = 'AI ' + str(index)
        index += 1
        # TODO check whether got error
        super(id, name)


class Game:
    '''Models a bridge game.
    
    players: list of Player objects
    bid (str): current highest bid, in '2S' (2 spades) format
    phase: 0=waiting, 1=bidding, 2=playing'''
    
    def __init__(self):
        self.players = []
        self.bid = None
        # TODO change phase specifications in comments as necessary
        self.phase = 0
    
    def addPlayer(self, id=None, name=None, isAI=False):
        '''Returns True if successfully added player, False otw.'''
        # check if player already in game
        for player in self.players:
            if player.id == id:
                return False
        if not isAI:
            self.players.append(Player(id, name))
        else:
            self.players.append(AI())
        return True
    
    def delPlayer(self, id=None, name=None, isAI=False):
        '''Returns True if successfully deleted player, False otw.'''
        if not isAI:
            for player in self.players:
                if player.id == id:
                    self.players.remove(player)
                    return True
        else:
            for player in self.players:
                if type(player) is AI:
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
