import os
from telegram.ext import CommandHandler, CallbackQueryHandler, Filters, \
    InlineQueryHandler, MessageHandler, Updater
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, \
    InlineQueryResultArticle, InputTextMessageContent, ParseMode, TelegramError
import logging
from bridge import Game
from telegram.utils.helpers import escape_markdown
from uuid import uuid4

# pass token with os config vars for security
#token = os.environ['TELEGRAM_TOKEN']
token = '1026774742:AAFkgzlK3KcyGt8XLzBxu33fqvfdQ-BpaQc'

# use_context=True for backward compatibility
updater = Updater(token=token, use_context=True)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# game data
games = {}  # {chat_id:Game}, chat_id in games = game created, vice versa
joinMessages = {}   # messages waiting for players to join


# handlers and other helper functions
def get_markup(context):
    '''Get the keyboard markup.'''
    firstRow, secondRow = [], []
    firstRow.append(InlineKeyboardButton("Join!", callback_data='1'))
    firstRow.append(InlineKeyboardButton("Quit...", callback_data='2'))
    secondRow.append(InlineKeyboardButton("Insert AI", callback_data='3'))
    secondRow.append(InlineKeyboardButton("Delete AI", callback_data='4'))
    return InlineKeyboardMarkup([firstRow, secondRow])

def start(update, context):
    # start in telegram actually CREATES a new Game, not start an existing Game
    chatId = update.effective_chat.id
    # private chat for initialising conversation only, cannot create new Game
    if update.effective_chat.type=='private':
        context.bot.send_message(chat_id=chatId, text='Add me to a group to play!')
        return
    if chatId in games:
        context.bot.send_message(
            chat_id=chatId, 
            text="A game has already started!"
        )
    else:
        games[chatId] = Game()
        joinMessages[chatId] = context.bot.send_message(
            chat_id=chatId,
            text="Waiting for players to join ...\nJoined players:",
            reply_markup=get_markup(context)
        )

def request_bid(player, update, context):
    '''Requests bid from player. Also handles bid if player is AI.'''
    chatId = update.effective_chat.id
    query = update.callback_query
    game = games[chatId]
    context.bot.send_message(
        chat_id=chatId, 
        text='@{}, your turn to bid!'.format(player['name'])
    )
    # handles bid for AI
    if player['id'] <= 0:
        bid, nextPlayer = game.bid(player)
        context.bot.send_message(
            chat_id=chatId, 
            text='@{}: {}'.format(player['name'], bid)
        )
        # TODO check if got recursive or stack error
        request_bid(nextPlayer, update, context)
    # handles bid for human
    # TODO change keyboard of bidding player(?)

def start_game(update, context):
    '''Handle bidding and playing phases.'''
    chatId = update.effective_chat.id
    query = update.callback_query
    game = games[chatId]
    firstPlayer = game.start()
    text = "Joined players:\n"
    text += '\n'.join([player['name'] for player in game.players])
    text += '\nGame has begun! Check your PMs to see your hands.'
    query.edit_message_text(text=text)
    # PM human players
    for player in game.players:
        if player['id'] > 0:    # human player's id > 0
            context.bot.send_message(
                chat_id=player['id'],
                text=str(player['hand'])
            )
    request_bid(firstPlayer, update, context)

def join(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = games[chatId]
    if game.full():
        context.bot.send_message(chat_id=chatId, text='Table already full!')
        return
    joinSuccess = game.add_human(user.id, user.first_name)
    if not joinSuccess:
        context.bot.send_message(
            chat_id=chatId,
            text='{}, you already joined the game!'.format(user.first_name)
        )
        return
    # joined, should be <=4 players otw all btns should've been removed
    try:
        context.bot.send_message(chat_id=user.id, text='Joined game!')
    except(TelegramError):
        text = '{}, please initiate a conversation with me @MYSGBridgeBot!'
        context.bot.send_message(chat_id=chatId, text=text.format(user.first_name))
        # undo the join
        game.del_Human(user.id, user.first_name)
        return
    if not game.full():
        text = "Waiting for players to join ...\nJoined players:\n"
        text += '\n'.join([player['name'] for player in game.players])
        query.edit_message_text(text=text, reply_markup=get_markup(context))
    else:
        start_game(update, context)

def quit(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = games[chatId]
    quitSuccess = game.del_human(user.id, user.first_name)
    if not quitSuccess:
        context.bot.send_message(
            chat_id=chatId,
            text = '{}, you haven\'t joined the game!'.format(user.first_name)
        )
    else:
        text = "Waiting for players to join ...\nJoined players:\n"
        text += '\n'.join([player['name'] for player in game.players])
        query.edit_message_text(text=text, reply_markup=get_markup(context))

def insert_AI(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = games[chatId]
    if game.full():
        context.bot.send_message(chat_id=chatId, text='Table already full!')
        return
    game.add_AI()
    if not game.full():
        text = "Waiting for players to join ...\nJoined players:\n"
        text += '\n'.join([player['name'] for player in game.players])
        query.edit_message_text(text=text, reply_markup=get_markup(context))
    else:
        start_game(update, context)

def delete_AI(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = games[chatId]
    delSuccess = game.del_AI()
    if not delSuccess:
        context.bot.send_message(chat_id=chatId, text = 'No AI in the game!')
    else:
        text = "Waiting for players to join ...\nJoined players:\n"
        text += '\n'.join([player['name'] for player in game.players])
        query.edit_message_text(text=text, reply_markup=get_markup(context))

def button(update, context):
    '''Pass the query to respective handlers.'''
    data = update.callback_query.data
    if data == '1':
        join(update, context)
    elif data == '2':
        quit(update, context)
    elif data == '3':
        insert_AI(update, context)
    elif data == '4':
        delete_AI(update, context)
    # CallbackQueries need to be answered, 
    # even if no notification to the user is needed
    # Some clients may have trouble otherwise.
    update.callback_query.answer()

def stop(update, context):
    '''Stop the game in progress.'''
    chatId = update.effective_chat.id
    if chatId not in games:
        context.bot.send_message(
            chat_id=chatId, 
            text='No game started!'
        )
        return
    # TODO ask user for confirmation to stop game
    game = games[chatId]
    if not game.started():   # phase of players joining, remove callback btns
        joinText = "Waiting for players to join ...\nJoined players:\n"
        joinText += '\n'.join([player['name'] for player in game.players])
        joinText += '\n(Game stopped)'
        joinMessages[chatId].edit_text(joinText)
    context.bot.send_message(
        chat_id=chatId, 
        text='Game stopped.'
    )
    del games[chatId]
    del joinMessages[chatId]
    
def action(update, context):
    '''Handle actions (bid/cards).
    
    Regex should only pass '@MYSGBridgeBot ...' here.
    Formats:
    bid: '1N', '2S', '3H', '4D', '5C', 'PASS'
    card: 'SA', 'HQ', 'DT', 'C8'
    case INsensitive
    '''
    actionStr = update.message.text.split(' ')[1]
    if actionStr[0] in '1234567P':  # bid
        # TODO bid
        pass
    elif actionStr[0] in 'SHDC':    # card
        # TODO play/call partner
        pass
    else:
        text = '''Invalid action! Formats:
            Bids:
            '@MYSGBridgeBot 1N' for 1 No trump
            '@MYSGBridgeBot 3S' for 3 Hearts
            '@MYSGBridgeBot PASS' for PASS
            Cards:
            '@MYSGBridgeBot SA' for Ace of Spades
            '@MYSGBridgeBot HQ' for Queen of Hearts
            '@MYSGBridgeBot DT' for Ten of Diamonds
            '@MYSGBridgeBot C8' for 8 of Clubs
        '''
    context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=text
    )
    

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


if __name__ == '__main__':
    # register handlers in the dispatcher
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(MessageHandler(
        Filters.regex(r'^@MYSGBridgeBot\s.'),
        action
    ))
    updater.dispatcher.add_error_handler(error)
    # start the bot
    updater.start_polling()
    # Run the bot until the user presses Ctrl-C or the process receives 
    # SIGINT, SIGTERM or SIGABRT
    updater.idle()
