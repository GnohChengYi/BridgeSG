import logging
import os
import time
import telegram.bot
from telegram.ext import CallbackQueryHandler, ChosenInlineResultHandler, \
    CommandHandler, DelayQueue, InlineQueryHandler, Updater
from telegram.utils.request import Request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, \
    InlineQueryResultArticle, InputTextMessageContent, ParseMode, TelegramError
from bridge import Game, Player

import testPostgres;

# (12 May) DelayQueues run forever. Might have problem in the future.
delayQueues = {}    # {chatId:DelayQueue}


def get_markup():
    firstRow, secondRow = [], []
    firstRow.append(InlineKeyboardButton("Join!", callback_data='1'))
    firstRow.append(InlineKeyboardButton("Quit...", callback_data='2'))
    secondRow.append(InlineKeyboardButton("Insert AI", callback_data='3'))
    secondRow.append(InlineKeyboardButton("Delete AI", callback_data='4'))
    return InlineKeyboardMarkup([firstRow, secondRow])


def update_join_message(chatId, buttons=True):
    game = Game.games[chatId]
    joinMessage = game.joinMessage
    text = "Waiting for players to join ...\nJoined players:\n"
    text += '\n'.join([player.name for player in game.players])
    if not buttons:
        delayQueues[chatId](joinMessage.edit_text, text=text)
        return
    delayQueues[chatId](
        joinMessage.edit_text,
        text=text,
        reply_markup=get_markup()
    )


def start(update, context):
    chatId = update.effective_chat.id
    if chatId not in delayQueues:
        # Official limit is 20 msg/1 min. Make it stricter here.
        delayQueues[chatId] = DelayQueue(burst_limit=19, time_limit_ms=61000)
    if chatId in Game.games:
        game = Game.games[chatId]
        delayQueues[chatId](
            context.bot.send_message,
            reply_to_message_id=game.joinMessage.message_id,
            chat_id=chatId,
            text='Game already started!'
        )
        return
    # create new Game and store in Game.games
    game = Game(chatId)
    game.joinMessage = context.bot.send_message(
        chat_id=chatId,
        text="Waiting for players to join ...\nJoined players:",
        reply_markup=get_markup(),
    )


def stop(update, context):
    chatId = update.effective_chat.id
    if chatId not in delayQueues:
        # Official limit is 20 msg/1 min. Make it stricter here.
        delayQueues[chatId] = DelayQueue(burst_limit=19, time_limit_ms=61000)
    if chatId not in Game.games:
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text='No game started!'
        )
        return
    game = Game.games[chatId]
    if game.phase == Game.JOIN_PHASE:  # no need update join msg aft game starts
        update_join_message(chatId, buttons=False)
    game.stop()
    delayQueues[chatId](
        context.bot.send_message,
        reply_to_message_id=game.joinMessage.message_id,
        chat_id=chatId,
        text='Game stopped.'
    )
    for player in game.players:
        if player.handMessage:
            delayQueues[chatId](player.handMessage.edit_text, 'Game stopped.')
    del game


def help(update, context):
    chatId = update.effective_chat.id
    if chatId not in delayQueues:
        # Official limit is 20 msg/1 min. Make it stricter here.
        delayQueues[chatId] = DelayQueue(burst_limit=19, time_limit_ms=61000)
    text = '[Floating bridge](https://en.wikipedia.org/wiki/Singaporean_bridge)\n'
    text += 'Start game: /start\n'
    text += 'Stop game: /stop\n'
    text += 'Show this: /help\n\n'
    text += 'For 1st timers, pm me @{} '.format(context.bot.username)
    text += 'so that I can pm you.\n\n'
    text += 'Type \'@{} hi\' to select bid/cards.\n'.format(
        context.bot.username)
    text += 'Wait for a while for bids/cards to appear.\n\n'
    text += 'I can only send <20 messages/minute'
    text += ", so please wait for 1 minute if I am not responding.\n"
    text += "If I did not respond within 1 minute, an error might have occured.\n"
    text += "Try /start to start a new game.\n\n"
    text += 'Good luck and have fun!'
    delayQueues[chatId](
        context.bot.send_message,
        chat_id=chatId,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )


def join(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = Game.games[chatId]
    if game.full():
        return
    joinSuccess = game.add_human(user.id, user.first_name)
    # slim possibility of failure due to full of players
    # (checked for fullness above and in game.add_human(...))
    if not joinSuccess:
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text='[{}](tg://user?id={}), '.format(user.first_name, user.id) +
            'quit/stop the game you joined (maybe in other chat) to join this game!',
            parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        context.bot.send_message(chat_id=user.id, text='Joined game!')
    except(TelegramError):
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text='[{}](tg://user?id={}), '.format(user.first_name, user.id) +
            'please initiate a conversation with me ' +
            '@{} !'.format(context.bot.username),
            parse_mode=ParseMode.MARKDOWN
        )
        # undo the join
        game.del_human(user.id)
        return
    if not game.full():
        update_join_message(chatId)
        return
    start_game(update, context)


def quit(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = Game.games[chatId]
    quitSuccess = game.del_human(user.id)
    if not quitSuccess:
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text='[{}](tg://user?id={}), '.format(user.first_name, user.id) +
            'you are not in the game of this chat!',
            parse_mode=ParseMode.MARKDOWN
        )
        return
    update_join_message(chatId)


def insert_AI(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    game = Game.games[chatId]
    if game.full():
        return
    # does not matter if add fail due to full players
    game.add_AI()
    if not game.full():
        update_join_message(chatId)
        return
    start_game(update, context)


def delete_AI(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    game = Game.games[chatId]
    delSuccess = game.del_AI()
    if not delSuccess:
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text='No AI in the game!'
        )
        return
    update_join_message(chatId)


def button(update, context):
    data = update.callback_query.data
    chatId = update.effective_chat.id
    try:
        if data == '1':
            join(update, context)
        elif data == '2':
            quit(update, context)
        elif data == '3':
            insert_AI(update, context)
        elif data == '4':
            delete_AI(update, context)
    except KeyError:    # chatId not in Game.games
        if chatId not in delayQueues:
            # Official limit is 20 msg/1 min. Make it stricter here.
            delayQueues[chatId] = DelayQueue(
                burst_limit=19, time_limit_ms=61000)
        try:
            update.callback_query.message.delete()
            text = 'I was restarted recently and lost memory. '
            text += 'Please ignore the unfinished games. '
            text += 'Sorry for the inconvenience. '
            delayQueues[chatId](
                context.bot.send_message,
                chat_id=chatId,
                text=text
            )
        except TelegramError:
            # "Message to delete not found": already deleted the message, no need to send lost-memory-message
            pass
    update.callback_query.answer()


def translate_bid(bid):
    '''Returns bid in a more readable form.'''
    if bid == Game.PASS:
        return 'PASS'
    bid = bid.replace('C', '♣️')
    bid = bid.replace('D', '♦️')
    bid = bid.replace('H', '❤️')
    bid = bid.replace('S', '♠️')
    bid = bid.replace('N', '🚫')
    return bid


def translate_card(card):
    '''Returns card in a more readable form.'''
    if not card:
        return
    card = card[::-1]
    card = card.replace('T', '10')
    card = card.replace('C', '♣️')
    card = card.replace('D', '♦️')
    card = card.replace('H', '❤️')
    card = card.replace('S', '♠️')
    return card


def translate_hand(hand):
    club, diamond, heart, spade = [], [], [], []
    for card in hand:
        if card[0] == 'C':
            club.append(card[1])
        elif card[0] == 'D':
            diamond.append(card[1])
        elif card[0] == 'H':
            heart.append(card[1])
        elif card[0] == 'S':
            spade.append(card[1])
    result = ''
    for suit, symbol in ((club, '♣️'), (diamond, '♦️'), (heart, '❤️'), (spade, '♠️')):
        line = symbol + ': ' + ' '.join(suit) + '\n'
        line = line.replace('T', '10')
        result += line
    return result


def thumb_url_bid(bid):
    if bid == Game.PASS:
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/81/waving-white-flag_1f3f3.png'
    if bid[1] == 'C':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/51/black-club-suit_2663.png'
    if bid[1] == 'D':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/51/black-diamond-suit_2666.png'
    if bid[1] == 'H':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/237/black-heart-suit_2665.png'
    if bid[1] == 'S':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/81/black-spade-suit_2660.png'
    if bid[1] == 'N':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/google/241/prohibited_1f6ab.png'


def thumb_url_card(card):
    if card[0] == 'C':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/125/black-club-suit_2663.png'
    if card[0] == 'D':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/126/black-diamond-suit_2666.png'
    if card[0] == 'H':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/125/black-heart-suit_2665.png'
    if card[0] == 'S':
        return 'https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/60/apple/126/black-spade-suit_2660.png'


def trick_text(game, next=True):
    text = 'Declarer: {}\n'.format(game.declarer.name)
    text += 'Bid: {}\n'.format(translate_bid(game.bid))
    text += 'Partner: {}\n\n'.format(translate_card(game.partnerCard))
    for i in range(len(game.players)):
        text += '{} ({}): {}\n'.format(
            game.players[i].name,
            game.players[i].tricks,
            translate_card(game.currentTrick[i])
        )
    if next:
        player = game.activePlayer
        text += '\n[{}](tg://user?id={}), '.format(player.name, player.id)
        text += 'your turn to play a card!'
    return text


def start_game(update, context):
    chatId = update.effective_chat.id
    update_join_message(chatId, buttons=False)
    delayQueues[chatId](
        context.bot.send_message,
        chat_id=chatId,
        text='Game starts now!'
    )
    game = Game.games[chatId]
    game.start()
    for player in game.players:
        if not player.isAI:
            player.handMessage = context.bot.send_message(
                chat_id=player.id,
                text='Your Hand:\n'+translate_hand(player.hand)
            )
    request_bid(chatId, context)


def request_bid(chatId, context):
    if chatId not in Game.games:    # everyone passed, game stopped
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text='Everyone passed! Game ended.'
        )
        return
    game = Game.games[chatId]
    player = game.activePlayer
    if game.phase == Game.CALL_PHASE:
        request_partner(chatId, context)
        return
    if player.isAI:
        bid = player.make_bid()
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text='{}: {}'.format(player.name, translate_bid(bid))
        )
        request_bid(chatId, context)
        return
    text = 'Current Bid: {}\n'.format(translate_bid(game.bid))
    if not game.declarer:
        text += 'Bidder: {}\n'.format(None)
    else:
        text += 'Bidder: {}\n'.format(game.declarer.name)
    text += '[{}](tg://user?id={}), '.format(player.name, player.id)
    text += 'your turn to bid!'
    delayQueues[chatId](
        context.bot.send_message,
        chat_id=chatId,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )


def request_partner(chatId, context):
    game = Game.games[chatId]
    player = game.activePlayer
    if player.isAI:
        player.call_partner()
        request_card(chatId, context)
        return
    delayQueues[chatId](
        context.bot.send_message,
        chat_id=chatId,
        text='[{}](tg://user?id={}), '.format(player.name, player.id) +
        'you won the bid! Choose your partner\'s card!',
        parse_mode=ParseMode.MARKDOWN
    )


def request_card(chatId, context):
    game = Game.games[chatId]
    if game.phase == Game.END_PHASE:
        conclude_game(chatId, context)
        return
    player = game.activePlayer
    if player is game.players[0]:
        delayQueues[chatId](
            context.bot.send_message,
            chat_id=chatId,
            text=trick_text(game),
            parse_mode=ParseMode.MARKDOWN
        )
    if player.isAI:
        card = player.play_card()
        if card:
            delayQueues[chatId](
                context.bot.send_message,
                chat_id=chatId,
                text=trick_text(game, next=player is not game.players[-1]),
                parse_mode=ParseMode.MARKDOWN
            )
            if player is game.players[-1]:
                game.complete_trick()
            request_card(chatId, context)


def conclude_game(chatId, context):
    game = Game.games[chatId]
    text = 'Congratulations!\n'
    for winner in game.winners:
        text += '[{}](tg://user?id={})\n'.format(winner.name, winner.id)
    text += 'You won the game!'
    delayQueues[chatId](
        context.bot.send_message,
        chat_id=chatId,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )
    for player in game.players:
        if player.handMessage:
            delayQueues[chatId](player.handMessage.edit_text, 'Game ended.')
    game.stop()


def inline_action(update, context):
    inlineQuery = update.inline_query
    query = inlineQuery.query
    if not query:
        return
    user = inlineQuery.from_user
    if user.id not in Player.players:
        return
    player = Player.players[user.id]
    game = player.game
    if player is not game.activePlayer:
        return
    results = []
    if game.phase == Game.BID_PHASE:
        for bid in game.valid_bids():
            results.append(InlineQueryResultArticle(
                id=bid,
                title=translate_bid(bid),
                input_message_content=InputTextMessageContent(
                    translate_bid(bid)),
                thumb_url=thumb_url_bid(bid)
            ))
    elif game.phase == Game.CALL_PHASE:
        # max 50 queryresults but 52 cards -> don't allow self-calling
        for card in Game.deck:
            if card not in player.hand:
                results.append(InlineQueryResultArticle(
                    id=card,
                    title=translate_card(card),
                    input_message_content=InputTextMessageContent(
                        translate_card(card)
                    ),
                    thumb_url=thumb_url_card(card)
                ))
    elif game.phase == Game.PLAY_PHASE:
        for card in player.valid_cards():
            results.append(InlineQueryResultArticle(
                id=card,
                title=translate_card(card),
                input_message_content=InputTextMessageContent(
                    translate_card(card)
                ),
                thumb_url=thumb_url_card(card)
            ))
    context.bot.answer_inline_query(
        inlineQuery.id,
        results,
        cache_time=2,
        is_personal=True
    )


def action(update, context):
    result = update.chosen_inline_result
    playerId = result.from_user.id
    player = Player.players[playerId]
    game = player.game
    chatId = player.game.id
    if game.phase == Game.BID_PHASE:
        bid = result.result_id
        if not player.make_bid(bid):
            delayQueues[chatId](
                context.bot.send_message,
                chat_id=chatId,
                text='Not your turn or invalid bid!'
            )
        request_bid(chatId, context)
    elif game.phase == Game.CALL_PHASE:
        card = result.result_id
        if not player.call_partner(card):
            delayQueues[chatId](
                context.bot.send_message,
                chat_id=chatId,
                text='Not your turn or invalid card!'
            )
            request_partner(chatId, context)
            return
        # start playing cards
        request_card(chatId, context)
    elif game.phase == Game.PLAY_PHASE:
        card = result.result_id
        if not player.play_card(card):
            delayQueues[chatId](
                context.bot.send_message,
                chat_id=chatId,
                text='Not your turn or invalid card!'
            )
        else:
            delayQueues[chatId](
                player.handMessage.edit_text,
                translate_hand(player.hand)
            )
            delayQueues[chatId](
                context.bot.send_message,
                chat_id=chatId,
                text=trick_text(game, next=player is not game.players[-1]),
                parse_mode=ParseMode.MARKDOWN
            )
            if player is game.players[-1]:
                game.complete_trick()
            request_card(chatId, context)


def error(update, context):
    logger.warning('\nUpdate "%s" caused error "%s"', update, context.error)


if __name__ == '__main__':
    token = os.environ['TELEGRAM_TOKEN']
    updater = Updater(
        token=token,
        use_context=True,
        request_kwargs={'read_timeout': 20, 'connect_timeout': 20}
    )
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(InlineQueryHandler(inline_action))
    updater.dispatcher.add_error_handler(error)
    updater.dispatcher.add_handler(ChosenInlineResultHandler(action))
    updater.start_polling()
    updater.idle()
