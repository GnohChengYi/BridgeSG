# handles everything in a bridge game
from uuid import uuid4
from random import shuffle

class Game:
    # {chatId:Game}, store all games
    games = {}
    deck = (
        ('SA','SK','SQ','SJ','ST','S9','S8','S7','S6','S5','S4','S3','S2'),
        ('HA','HK','HQ','HJ','HT','H9','H8','H7','H6','H5','H4','H3','H2'),
        ('DA','DK','DQ','DJ','DT','D9','D8','D7','D6','D5','D4','D3','D2'),
        ('CA','CK','CQ','CJ','CT','C9','C8','C7','C6','C5','C4','C3','C2')
    )
    bids = (
        '1C', '1D', '1H', '1S', '1N', 
        '2C', '2D', '2H', '2S', '2N', 
        '3C', '3D', '3H', '3S', '3N', 
        '4C', '4D', '4H', '4S', '4N', 
        '5C', '5D', '5H', '5S', '5N', 
        '6C', '6D', '6H', '6S', '6N', 
        '7C', '7D', '7H', '7S', '7N'
    )
    PASS = 'PASS'
    
    def __init__(self, id):
        self.id = id
        self.players = []
        self.phase = 0  # 0:join, 1:bid/call, 2:play
        self.activePlayer = None
        self.declarer = None
        self.bid = Game.PASS   # (''=empty str=PASS), 1N, 2S, 3H, 4D, 5C, etc.
        self.trump = '' # N, S, H, D, C
        self.contract = 0   # 7, 8, 9, 10, 11, 12, 13
        Game.games[id] = self

    def full(self):
        return len(self.players) >= 4
    
    def started(self):
        return self.phase>0
    
    def add_human(self, id, name):
        if self.full() or id in Player.players:
            return False
        player = Player(id, name)
        self.players.append(player)
        player.game = self
        return True
    
    def del_human(self, id):
        if id not in Player.players:    # not in any game
            return False
        player = Player.players[id]
        if player not in self.players:  # not in this game
            return False
        self.players.remove(player)
        del player
        del Player.players[id]
        return True
    
    def add_AI(self):
        if self.full():
            return False
        id = uuid4()
        name = 'AI ' + str(id)[:5]
        player = Player(id, name, isAI=True)
        self.players.append(player)
        player.game = self
        return True
    
    def del_AI(self):
        for player in self.players:
            if player.isAI:
                self.players.remove(player)
                del Player.players[player.id]
                del player
                return True
        return False
    
    def start(self):
        self.phase = 1
        dealDeck = list(Game.deck)
        shuffle(dealDeck)
        self.players[0].hand = dealDeck[:13]
        self.players[1].hand = dealDeck[13:26]
        self.players[2].hand = dealDeck[26:39]
        self.players[3].hand = dealDeck[39:]
        self.activePlayer = self.players[0]
    
    def stop(self):
        for player in self.players:
            del Player.players[player.id]
            del player
        del Game.games[self.id]
    
    def next(self):
        self.activePlayer = \
            self.players[(self.players.index(self.activePlayer) + 1) % 4]
    
    def valid_bids(self):
        if self.bid == Game.PASS:
            return (Game.PASS,) + Game.bids
        index = Game.bids.index(self.bid)
        return (Game.PASS,) + Game.bids[index:]


class Player:
    # {userId:Player}, store all players
    players = {}
    
    def __init__(self, id, name, isAI=False):
        self.id = id
        self.name = name
        self.game = None
        self.isAI = isAI
        self.hand = []
        Player.players[id] = self
    
    def make_bid(self, bid=Game.PASS):
        if self.isAI:
            # TODO code AI logic
            self.game.next()
            return Game.PASS
        # TODO check validity
        if bid!='':
            self.game.declarer = self
            self.game.bid = bid
        # TODO only if valid
        self.game.next()
