# handles everything in a bridge game
from uuid import uuid4
from random import choice, shuffle

class Game:
    # {chatId:Game}, store all games
    games = {}
    suits = 'CDHS'
    numbers = 'AKQJT98765432'
    deck = (
        'CA','CK','CQ','CJ','CT','C9','C8','C7','C6','C5','C4','C3','C2',
        'DA','DK','DQ','DJ','DT','D9','D8','D7','D6','D5','D4','D3','D2',
        'HA','HK','HQ','HJ','HT','H9','H8','H7','H6','H5','H4','H3','H2',
        'SA','SK','SQ','SJ','ST','S9','S8','S7','S6','S5','S4','S3','S2'
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
    JOIN_PHASE = 0
    BID_PHASE = 1
    CALL_PHASE = 2
    PLAY_PHASE = 3
    END_PHASE = 4
    
    def __init__(self, id):
        self.id = id
        self.joinMessage = None
        self.players = []   # leading player of current trick always first
        self.phase = Game.JOIN_PHASE
        self.activePlayer = None
        self.declarer = None
        self.bid = Game.PASS   # 1N, 2S, 3H, 4D, 5C, etc.
        self.trump = '' # N, S, H, D, C
        self.contract = 0   # 7, 8, 9, 10, 11, 12, 13
        self.partnerCard = None
        # list of cards, corresponds to current order of players
        # None if not play card yet
        self.currentTrick = [None]*4
        self.trumpBroken = False
        self.totalTricks = 0    # declarer+partner's tricks, update in end phase
        self.winners = set()
        Game.games[id] = self

    def full(self):
        return len(self.players) >= 4
    
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
        self.phase = Game.BID_PHASE
        dealDeck = list(Game.deck)
        shuffle(dealDeck)
        key = lambda x: (x[0], 'AKQJT98765432'.index(x[1]))
        self.players[0].hand = sorted(dealDeck[:13], key=key)
        self.players[1].hand = sorted(dealDeck[13:26], key=key)
        self.players[2].hand = sorted(dealDeck[26:39], key=key)
        self.players[3].hand = sorted(dealDeck[39:], key=key)
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
        return (Game.PASS,) + Game.bids[index+1:]
    
    def start_play(self):
        # 2N for 2 No Trump self.bid. '' for no trump self.trump.
        self.trump = self.bid[1] if self.bid[1]!='N' else ''
        self.contract = int(self.bid[0]) + 6
        self.phase = Game.PLAY_PHASE
        # next player lead if have trump, declarer lead if no trump
        if self.trump:
            self.next()
        # reorder players list so that first player leads
        index = self.players.index(self.activePlayer)
        self.players = self.players[index:] + self.players[:index]
    
    '''
    def winning_card(self):
        if self.currentTrick[0]==None:
            return
        suit = self.currentTrick[0][0]
        if self.trump in self.currentTrick:
            suit = self.trump
        cardsOfSuit = [c for c in self.currentTrick if c and c[0]==suit]
        cardsOfSuit.sort(key=lambda card:Game.numbers.index(card[1]))
        return cardsOfSuit[0]
    
    def highest_card(self, cards):
        # don't care about leading suit
        trump = self.trump
        suit = self.currentTrick[0][0]
        if card1[0]==trump and card2[0]==trump:
            return
    '''
    
    def complete_trick(self):
        if not self.trump or \
            self.trump not in [card[0] for card in self.currentTrick]:
            suit = self.currentTrick[0][0]
        else:
            suit = self.trump
        cardsOfSuit = [card for card in self.currentTrick if card[0]==suit]
        cardsOfSuit.sort(key=lambda card:Game.numbers.index(card[1]))
        highestCard = cardsOfSuit[0]
        index = self.currentTrick.index(highestCard)
        winner = self.players[index]
        winner.tricks += 1
        self.activePlayer = winner
        self.players = self.players[index:] + self.players[:index]
        self.currentTrick = [None]*4
        if len(self.activePlayer.hand) == 0:    # next player no more cards=end
            self.conclude()
    
    def conclude(self):
        self.phase = Game.END_PHASE
        self.totalTricks = self.declarer.tricks
        if self.declarer.partner is not self.declarer:
            self.totalTricks += self.declarer.partner.tricks
        self.winners = {self.declarer, self.declarer.partner}
        if self.totalTricks < self.contract:
            self.winners = set(self.players) - self.winners


class Player:
    # {userId:Player}, store all players
    players = {}
    
    def __init__(self, id, name, isAI=False):
        self.id = id
        self.name = name
        self.game = None
        self.isAI = isAI
        self.hand = []
        self.handMessage = None
        self.partner = None
        self.tricks = 0
        Player.players[id] = self
    
    def make_bid(self, bid=Game.PASS):
        game = self.game
        if self is not game.activePlayer:
            return
        validBids = game.valid_bids()
        if self.isAI:
            # TODO code AI logic
            bid = choice(validBids[:2])
        if bid not in validBids:
            return
        if bid!=Game.PASS:
            game.declarer = self
            game.bid = bid
        game.next()
        # everyone passed, nobody bidded
        if game.activePlayer==game.players[0] and game.bid==Game.PASS:
            game.stop()
        if game.activePlayer == game.declarer:
            game.phase = Game.CALL_PHASE
        return bid
    
    def call_partner(self, card='SA'):
        game = self.game
        if self is not game.activePlayer:
            return
        if self.isAI:
            # TODO code AI logic
            card = choice(Game.deck)
        if card not in Game.deck:
            return
        game.partnerCard = card
        for player in self.game.players:
            if card in player.hand:
                # only care who is declarer's partner
                # play whole game and see
                # whether declarer and partner (possibly self) fulfill contract
                self.partner = player
                break
        game.start_play()
        return card
    
    def play_card(self, card='SA'):
        game = self.game        
        if self is not game.activePlayer:
            return
        validCards = self.valid_cards()
        if self.isAI:
            # pass validCards so that no need to call valid_cards() again in AI
            card = self.choose_card_AI(validCards)
        if card not in validCards:
            return
        self.hand.remove(card)
        index = game.players.index(self)
        game.currentTrick[index] = card
        # call game.complete_trick() in bot.py after showing current tricks
        if self is not game.players[-1]:
            game.next()
        if not game.trumpBroken and card[0]==game.trump:
            game.trumpBroken = True
        return card
    
    def choose_card_AI(self, validCards):
        '''
        game = self.game
        trick = game.currentTrick
        if not trick[0]:    # self lead
            return choice(validCards)
        trump = game.trump
        winningCard = game.winning_card()
        trumps = {card for card in validCards if card[0]==trump}
        nonTrumps = set(validCards) - trumps
        if len(trumps)>0 and 
        
        validSuits = {card[0] for card in validCards}
        if trump in validSuits:
            highCardCandidates = [card for card in validCards if card[0]==trump]
            highCardCandidates.sort(key=lambda card:Game.numbers.index(card[1]))
            highCard = highCardCandidates[0]
        
        
        if trump and trump not in trick:
            suit = trick[0][0]
            cardsOfSuit = [card for card in trick if card and card[0]==suit]
        if canWin:
            # play high card
            # TODO
            pass
        else:
            # play low card
            # TODO
            pass
        ''' 
        return choice(validCards)

    def valid_cards(self):
        leadingCard = self.game.currentTrick[0]
        game = self.game
        if not leadingCard:
            result = self.hand
            if game.trump and not game.trumpBroken:
                result = list(filter(lambda card:card[0]!=game.trump, result))
            return result
        leadingSuit = leadingCard[0]
        result = [card for card in self.hand if card[0]==leadingSuit]
        if len(result)==0:  # can break trump now
            return self.hand
        return result
