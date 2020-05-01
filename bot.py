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
    if not game.started():  # no need to update join message after game started
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
    # does not matter if add fail due to full
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
    request_bid(update, context)

def translate_bid(bid):
    '''Returns bid in a more readable form.'''
    # TODO
    if bid == Game.PASS:
        return 'PASS'
    return bid

def request_bid(update, context):
    chatId = update.effective_chat.id
    game = Game.games[chatId]
    player = game.activePlayer
    if player is game.declarer:
        # TODO end bid, call partner
        return
    if player.isAI:
        bid = player.make_bid()
        context.bot.send_message(
            chat_id=chatId, 
            text='{}:  {}'.format(player.name, translate_bid(bid))
        )
        request_bid(update, context)
        return
    context.bot.send_message(
        chat_id=chatId,
        text='[{}](tg://user?id={}), your turn to bid!'
            .format(player.name, player.id),
        parse_mode=ParseMode.MARKDOWN
    )

def inline_action(update, context):
    # TODO card
    inlineQuery = update.inline_query
    query = inlineQuery.query
    user = inlineQuery.from_user
    if user.id not in Player.players:
        return
    results = []
    player = Player.players[user.id]
    game = player.game
    for bid in game.valid_bids():
        results.append(InlineQueryResultArticle(
            id=bid,
            title=bid,
            input_message_content=InputTextMessageContent(translate_bid(bid))
        ))
    context.bot.answer_inline_query(inlineQuery.id, results)

def action():
    print('action')
    print('update:', update)

def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


if __name__ == '__main__':
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(InlineQueryHandler(inline_action))
    # TODO try again for a while, if still cannot then use messagehandler
    updater.dispatcher.add_handler(ChosenInlineResultHandler(action))
    updater.start_polling()
    updater.idle()
    
    
