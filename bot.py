import os
from telegram.ext import ChosenInlineResultHandler, CommandHandler, \
    CallbackQueryHandler, InlineQueryHandler, Updater
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, \
    InlineQueryResultArticle, InputTextMessageContent, ParseMode, TelegramError
import logging
from bridge import Game, Player

# TODO pass token with os config vars for security
#token = os.environ['TELEGRAM_TOKEN']
token = '1026774742:AAFkgzlK3KcyGt8XLzBxu33fqvfdQ-BpaQc'

updater = Updater(token=token, use_context=True)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# {chatId:Message}, messages waiting for players to join
joinMessages = {}   


def get_markup():
    firstRow, secondRow = [], []
    firstRow.append(InlineKeyboardButton("Join!", callback_data='1'))
    firstRow.append(InlineKeyboardButton("Quit...", callback_data='2'))
    secondRow.append(InlineKeyboardButton("Insert AI", callback_data='3'))
    secondRow.append(InlineKeyboardButton("Delete AI", callback_data='4'))
    return InlineKeyboardMarkup([firstRow, secondRow])

def update_join_message(chatId, buttons=True):
    game = Game.games[chatId]
    joinMessage = joinMessages[chatId]
    text = "Waiting for players to join ...\nJoined players:\n"
    text += '\n'.join([player.name for player in game.players])
    if not buttons:
        joinMessage.edit_text(text=text)
        return
    joinMessage.edit_text(text=text, reply_markup=get_markup())

def start(update, context):
    chatId = update.effective_chat.id
    if chatId in Game.games:
        context.bot.send_message(
            reply_to_message_id=joinMessages[chatId].message_id,
            chat_id=chatId, 
            text='Game already started!'
        )
        return
    # create new Game and store in Game.games
    Game(chatId)
    joinMessages[chatId] = context.bot.send_message(
        chat_id=chatId,
        text="Waiting for players to join ...\nJoined players:",
        reply_markup=get_markup(),
    )

def stop(update, context):
    chatId = update.effective_chat.id
    if chatId not in Game.games:
        context.bot.send_message(chat_id=chatId, text='No game started!')
        return
    game = Game.games[chatId]
    if game.phase==Game.JOIN_PHASE:  # no need update join msg aft game starts
        update_join_message(chatId, buttons=False)
    game.stop()
    joinMessage = joinMessages[chatId]
    context.bot.send_message(
        reply_to_message_id=joinMessages[chatId].message_id,
        chat_id=chatId, 
        text='Game stopped.'
    )
    del joinMessages[chatId]

def join(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query 
    user = query.from_user
    game = Game.games[chatId]
    if game.full():
        return
    joinSuccess = game.add_human(user.id, user.first_name)
    # slim possibility of failure due to full of players
    # (checked for fullness above and in game.add_humen(...))
    if not joinSuccess:
        context.bot.send_message(
            chat_id=chatId,
            text='[{}](tg://user?id={}), '.format(user.first_name, user.id)+
                'you already joined a game (possibly in another chat).',
            parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        context.bot.send_message(chat_id=user.id, text='Joined game!')
    except(TelegramError):
        context.bot.send_message(
            chat_id=chatId,
            text = '[{}](tg://user?id={}), '.format(user.first_name, user.id)+
            'please initiate a conversation with me @MYSGBridgeBot!',
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
        context.bot.send_message(
            chat_id=chatId,
            text='[{}](tg://user?id={}), '.format(user.first_name, user.id)+
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
        context.bot.send_message(chat_id=chatId, text = 'No AI in the game!')
        return
    update_join_message(chatId)

def button(update, context):
    data = update.callback_query.data
    if data == '1':
        join(update, context)
    elif data == '2':
        quit(update, context)
    elif data == '3':
        insert_AI(update, context)
    elif data == '4':
        delete_AI(update, context)
    update.callback_query.answer()

def start_game(update, context):
    chatId = update.effective_chat.id
    update_join_message(chatId, buttons=False)
    context.bot.send_message(chat_id=chatId, text='Game starts now!')
    game = Game.games[chatId]
    game.start()
    for player in game.players:
        if not player.isAI:
            player.handMessage = context.bot.send_message(
                chat_id=player.id, 
                text='Your Hand:\n'+str(player.hand)
            )
    request_bid(chatId, context)

def translate_bid(bid):
    '''Returns bid in a more readable form.'''
    # TODO
    if bid == Game.PASS:
        return 'PASS'
    return bid

def translate_card(card):
    '''Returns card in a more readable form.'''
    # TODO
    return card

def request_bid(chatId, context):
    if chatId not in Game.games:    # everyone passed, game stopped
        context.bot.send_message(
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
        context.bot.send_message(
            chat_id=chatId, 
            text='{}:  {}'.format(player.name, translate_bid(bid))
        )
        request_bid(chatId, context)
        return
    text = 'Current Bid: {}\n'.format(game.bid)
    if not game.declarer:
        text += 'Bidder       : {}\n'.format(None)
    else:
        text += 'Bidder       : {}\n'.format(game.declarer.name)
    text += '[{}](tg://user?id={}), '.format(player.name, player.id)
    text += 'your turn to bid!'
    context.bot.send_message(
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
    context.bot.send_message(
        chat_id=chatId, 
        text='[{}](tg://user?id={}), '.format(player.name, player.id)+
            'you won the bid! Choose your partner\'s card!',
        parse_mode=ParseMode.MARKDOWN
    )

def request_card(chatId, context):
    game = Game.games[chatId]
    player = game.activePlayer
    if player.isAI:
        card = player.play_card()
        context.bot.send_message(
            chat_id=chatId, 
            text='{}: {}'.format(player.name, translate_card(card))
        )
        request_card(chatId, context)
        return
    text  = 'Declarer: {}\n'.format(game.declarer.name)
    text += 'Bid       : {}\n'.format(game.bid)
    text += 'Partner : {}\n'.format(game.partnerCard)
    for i in range(len(game.players)):
        text += '{} ({}): {}\n'.format(
            game.players[i].name,
            game.players[i].tricks,  
            game.currentTrick[i]
        )
    text += '[{}](tg://user?id={}), '.format(player.name, player.id)
    text += 'you turn to play a card!'
    context.bot.send_message(
        chat_id=chatId, 
        text=text, 
        parse_mode=ParseMode.MARKDOWN
    )

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
                title=bid,
                input_message_content=InputTextMessageContent(translate_bid(bid))
            ))
    elif game.phase == Game.CALL_PHASE:
        # max 50 results for inline query but 52 cards
        # for now don't allow self-calling
        # TODO use query to search for card
        for card in Game.deck:
            if card not in player.hand:
                results.append(InlineQueryResultArticle(
                    id=card,
                    title=translate_card(card),
                    input_message_content=InputTextMessageContent(
                        translate_card(card)
                    )
                ))
    elif game.phase == Game.PLAY_PHASE:
        for card in player.valid_cards():
            results.append(InlineQueryResultArticle(
                id=card,
                title=translate_card(card),
                input_message_content=InputTextMessageContent(
                    translate_card(card)
                )
            ))
    context.bot.answer_inline_query(inlineQuery.id, results)

def action(update, context):
    result = update.chosen_inline_result
    playerId = result.from_user.id
    player = Player.players[playerId]
    game = player.game
    chatId = player.game.id
    if game.phase == Game.BID_PHASE:
        bid = result.result_id
        if not player.make_bid(bid):
            context.bot.send_message(
                chat_id=chatId, 
                text='Not your turn or invalid bid!'
            )
        request_bid(chatId, context)
    elif game.phase == Game.CALL_PHASE:
        card = result.result_id
        if not player.call_partner(card):
            context.bot.send_message(
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
            context.bot.send_message(
                chat_id=chatId, 
                text='Not your turn or invalid card!'
            )
        else:
            player.handMessage.edit_text(str(player.hand))
        request_card(chatId, context)

def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


if __name__ == '__main__':
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(InlineQueryHandler(inline_action))
    # TODO uncomment add_error_handler for final product
    #updater.dispatcher.add_error_handler(error)
    updater.dispatcher.add_handler(ChosenInlineResultHandler(action))
    updater.start_polling()
    updater.idle()
    
    
