# handles everything in a bridge game
from uuid import uuid4
from random import choice, shuffle


def calculate_HCP(hand):
    """Calculate High Card Points (HCP) for a given hand."""
    numPoints = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}
    return sum(numPoints.get(card[1], 0) for card in hand)

def group_cards_by_suit(hand):
    """Group cards by suit and return a dictionary."""
    suitCards = {suit: [] for suit in Game.suits}
    for card in hand:
        suitCards[card[0]].append(card)
    return suitCards

calculate_TP = lambda hand: calculate_HCP(hand) + sum(max(0, len(cards) - 4) for cards in group_cards_by_suit(hand).values())

def sort_cards_by_number(cards):
    """Sort cards by their number based on Game.numbers."""
    return sorted(cards, key=lambda card: Game.numbers.index(card[1]))

def filter_non_trump_cards(cards, trump):
    """Filter out non-trump cards from a list of cards."""
    return [card for card in cards if card[0] != trump]

def lowest_card(cards, trump):
    """Returns card with the lowest number that is not trump."""
    nonTrumps = filter_non_trump_cards(cards, trump)
    if not nonTrumps:
        return cards[-1]  # All trump, last card is lowest
    return sort_cards_by_number(nonTrumps)[-1]

# Refactored compare_cards function
def compare_cards(card1, card2, leadingSuit, trump):
    """Compare two cards and determine which is higher."""
    if card1[0] == card2[0]:  # Same suit
        return (Game.numbers.index(card2[1]) - Game.numbers.index(card1[1]))
    if card1[0] in (trump, leadingSuit) and card2[0] not in (trump, leadingSuit):
        return 1
    if card2[0] in (trump, leadingSuit) and card1[0] not in (trump, leadingSuit):
        return -1
    # both cards not leading suit and not trump
    return 0

def deal_hands(deck):
    """Shuffle and deal hands to players."""
    shuffle(deck)
    return [deck[i:i + 13] for i in (0, 13, 26, 39)]

def validate_hands(hands):
    """Ensure all hands meet the minimum Total Points (TP) requirement."""
    return all(calculate_TP(hand) >= 8 for hand in hands)

def assign_hands_to_players(players, hands):
    """Assign sorted hands to players."""
    for i, hand in enumerate(hands):
        players[i].hand = sort_cards_by_number(hand)

def start_game(game):
    """Start the game by dealing cards and setting the active player."""
    dealDeck = list(Game.deck)
    while True:
        hands = deal_hands(dealDeck)
        if validate_hands(hands):
            assign_hands_to_players(game.players, hands)
            break
    game.activePlayer = game.players[0]
    game.phase = Game.BID_PHASE


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
        self.players = []   # leading player of current trick always first
        self.phase = Game.JOIN_PHASE
        self.activePlayer = None
        self.declarer = None
        self.bid = Game.PASS   # 1N, 2S, 3H, 4D, 5C, etc.
        self.trump = '' # ''=N, S, H, D, C
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
        # make sure no repeated ids
        while True:
            id = str(uuid4())[:8]
            if id not in Player.players:
                break
        name = 'AI ' + id[:5]
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
        #print('declarer:', self.declarer.name)
        #print('bid:', self.bid)
        #print('partner:', self.partnerCard)
    
    def winning_index(self):
        if not self.currentTrick[0]:
            return
        numbers = Game.numbers
        trick = self.currentTrick
        leadingSuit = trick[0][0]
        trump = self.trump
        winIndex = 0
        for i in range(len(trick)):
            if not trick[i]:
                break
            card1 = trick[winIndex]
            card2 = trick[i]
            if card1[0]==card2[0]: # same suit
                if numbers.index(card2[1]) < numbers.index(card1[1]):
                    winIndex = i
            elif card1[0]!=trump and card2[0]==trump:
                winIndex = i
            elif  card1[0] != trump and card2[0]==leadingSuit:
                winIndex = i
        return winIndex
    
    def complete_trick(self):
        winIndex = self.winning_index()
        winner = self.players[winIndex]
        winner.tricks += 1
        self.activePlayer = winner
        self.players = self.players[winIndex:] + self.players[:winIndex]
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

    def start(self):
        start_game(self)

    def stop(self):
        """Stop the game and clean up resources."""
        self.phase = Game.END_PHASE
        for player in self.players:
            if player.id in Player.players:
                del Player.players[player.id]
        if self.id in Game.games:
            del Game.games[self.id]


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
        if isAI:
            self.maxBid = None
            self.enemies = []
        Player.players[id] = self
    
    def make_bid(self, bid=Game.PASS):
        game = self.game
        if self is not game.activePlayer:
            return
        validBids = game.valid_bids()
        if self.isAI:
            bid = self.choose_bid_AI(validBids)
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
            card = self.choose_partner_AI()
        if card not in Game.deck:
            print('ERROR: Called card {} not in deck!'.format(card))
            return
        game.partnerCard = card
        for player in game.players:
            if player.isAI:
                # initialise enemies for AI player
                player.enemies = [p for p in game.players if p is not player]
            if card in player.hand:
                # only care who is declarer's partner
                # play whole game and see
                # whether declarer and partner (possibly self) fulfill contract
                self.partner = player
                # remove declarer from enemies if player is partner
                if player.isAI and self in player.enemies:
                    player.enemies.remove(self)
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
        # self played partner card -> update AI enemies
        if card==game.partnerCard:
            for player in game.players:
                if not player.isAI or player is self:
                    # self is partner, already know who are enemies
                    continue
                if player is game.declarer:
                    if self in player.enemies:
                        # declarer remove self (partner) from enemies
                        player.enemies.remove(self)
                else:
                    # non-declaring side update enemies, self is declarer's partner
                    player.enemies = [game.declarer, self]
        #print(self.name, self.hand, card)
        return card
    
    def choose_bid_AI(self, validBids):
        if not self.maxBid:
            HCP = calculate_HCP(self.hand)
            suitLengths = {
                suit: len([card for card in self.hand if card[0] == suit])
                for suit in Game.suits
            }
            maxLength = max(suitLengths.values())
            minLength = min(suitLengths.values())
            if maxLength <= 4 and minLength >= 2:  # Try no trump
                maxBidNum = round(0.25 * HCP - 1.75)
                maxBidNum = min(maxBidNum, 7)
                self.maxBid = str(maxBidNum) + 'N' if maxBidNum > 0 else Game.PASS
            else:   # ind preferred trump
                # many suits longest -> take highest suit (S>H>D>C)
                for suit in Game.suits[::-1]:
                    if suitLengths[suit] == maxLength:
                        preferredSuit = suit
                        break
                maxBidNum = round(0.23 * HCP + 0.70 * maxLength - 4.39)
                maxBidNum = min(maxBidNum, 7)
                self.maxBid = str(maxBidNum) + preferredSuit if maxBidNum > 0 else Game.PASS
        if self.maxBid == Game.PASS or self.maxBid not in validBids:
            return Game.PASS
        if self.game.bid[1] == self.maxBid[1]:
            return Game.PASS
        for bid in validBids:
            if bid[1] == self.maxBid[1]:
                return bid
    
    def choose_partner_AI(self):
        game = self.game
        trump = game.bid[1] # start_play not called yet so game.trump not set yet
        if trump != 'N':
            aceTrump = trump + 'A'
            if aceTrump not in self.hand:
                return aceTrump
            kingTrump = trump + 'K'
            if kingTrump not in self.hand:
                return kingTrump
        for card in ('SA', 'HA', 'DA', 'CA', 'SK', 'HK', 'DK', 'CK'):
            if card not in self.hand:
                return card
        return choice(Game.deck)

    def choose_card_AI(self, validCards):
        game = self.game
        winIndex = game.winning_index()
        if winIndex==None:
            # self is leading player, play random card
            return choice(validCards)
        winPlayer = game.players[winIndex]
        if winPlayer not in self.enemies:
            # partner winning -> play lowest card
            return lowest_card(validCards, game.trump)
        winCard = game.currentTrick[winIndex]
        leadingSuit = game.currentTrick[0][0]
        lowestWinningCard = None
        for card in validCards:
            if compare_cards(card, winCard, leadingSuit, game.trump)==1:
                # validCards sorted when dealing. 
                if self is not game.players[-1]:
                    # Plays highest card to win if not last player.
                    return card
                else:
                    # Last player. Track lowest card that can win.
                    lowestWinningCard = card
        if lowestWinningCard:
            # Last player. Plays lowest card that can win.
            return lowestWinningCard
        # cannot win -> play lowest card
        return lowest_card(validCards, game.trump)

    def valid_cards(self):
        leadingCard = self.game.currentTrick[0]
        game = self.game
        if not leadingCard:
            result = self.hand
            if game.trump and not game.trumpBroken:
                result = list(filter(lambda card:card[0]!=game.trump, result))
            return result if len(result)>0 else self.hand
        leadingSuit = leadingCard[0]
        result = [card for card in self.hand if card[0]==leadingSuit]
        return result if len(result)>0 else self.hand


def trial():
    game = Game(0)
    for i in range(4):
        game.add_AI()
    game.start()
    while game.phase == Game.BID_PHASE:
        game.activePlayer.make_bid()
    if not game.declarer:  # everyone passed, game stopped 
        del game
        return
    game.declarer.call_partner()
    while game.phase != Game.END_PHASE:
        for i in range(4):
            game.activePlayer.play_card()
        game.complete_trick()
    game.stop()
    if game.totalTricks - game.contract >= 1:
        del game
        return True
    del game
    return False

def run_trials(num):
    contractAchieved = 0
    for i in range(num):
        if trial():
            contractAchieved += 1
    print('declarer win/almost win rate: {:.3f}'.format(contractAchieved/num))


if __name__=='__main__':
    run_trials(10000)
