from telegram.ext import CommandHandler, CallbackQueryHandler, Filters, \
    MessageHandler, Updater
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# TODO remove token, use os.env...(follow heroku telegram bot tutorial), otw other ppl can control my bot
token = '1026774742:AAFkgzlK3KcyGt8XLzBxu33fqvfdQ-BpaQc'

# use_context=True for backward compatibility
updater = Updater(token=token, use_context=True)

# set up logging to know when and why things don't work as expected
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
    )
logger = logging.getLogger(__name__)

# game data
# data[chatId] = data for that chat
phases = {} # TODO check gamePhase: 0=none, 1=join, 2=bid, 3=play
tables = {} # TODO tables[chatId][user(?)] = hand ...
joinMessages = {}   # messages waiting for players to join


class Player:
    '''Models the player of a bridge game'''
    
    def __init__(self, id, first_name):
        # User id is positive int, AI id is negative int
        self.id = id
        print(first_name, id)
        self.first_name = first_name
        self.hand = []
        self.partner = None


# handlers and other helper functions
def get_markup(join=True, quit=True, addBot=True, delBot=True):
    '''Get a keyboard with the given buttons.'''
    firstRow, secondRow = [], []
    if join:
        firstRow.append(InlineKeyboardButton("Join!", callback_data='1'))
    if quit:
        firstRow.append(InlineKeyboardButton("Quit...", callback_data='2'))
    if addBot:
        secondRow.append(InlineKeyboardButton("Insert AI", callback_data='3'))
    if delBot:
        secondRow.append(InlineKeyboardButton("Delete AI", callback_data='4'))
    return InlineKeyboardMarkup([firstRow, secondRow])

def start(update, context):
    chatId = update.effective_chat.id
    phase = phases[chatId] if chatId in phases else 0
    if phase > 0:
        context.bot.send_message(
            chat_id=chatId, 
            text="A game has already started!"
        )
    elif phase == 0:
        phases[chatId] = 1
        # initialises tables[chatId]
        tables[chatId] = []
        joinMessages[chatId] = context.bot.send_message(
            chat_id=chatId,
            text="Waiting for players to join ...\nJoined players:",
            reply_markup=get_markup()
        )
    else:
        raise Exception('gamePhase  !number  or  <0')

def join(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    players = tables[chatId]
    if user.id in [player.id for player in players]:
        context.bot.send_message(
            chat_id=chatId,
            text = '{}, you already joined the game!'.format(user.first_name)
        )
    else:   # should be <4 players otw all btns should've been removed
        players.append(Player(user.id, user.first_name))
        if len(players) < 4:
            text = "Waiting for players to join ...\nJoined players:\n"
            text += '\n'.join([player.first_name for player in players])
            query.edit_message_text(text=text, reply_markup=get_markup())
        else:
            phases[chatId] = 2
            text = "Joined players:\n"
            text += '\n'.join([player.first_name for player in players])
            text += '\nGame has begun! Check your PMs to see your hands.'
            query.edit_message_text(text=text)
            # TODO handle game begun

def quit(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    players = tables[chatId]
    if user.id not in [player.id for player in players]:
        context.bot.send_message(
            chat_id=chatId,
            text = '{}, you haven\'t joined the game!'.format(user.first_name)
        )
    else:
        for player in players:
            if player.id == user.id:
                players.remove(player)
                break
        text = "Waiting for players to join ...\nJoined players:\n"
        text += '\n'.join([player.first_name for player in players])
        query.edit_message_text(text=text, reply_markup=get_markup())

def button(update, context):
    '''Pass the query to respective handlers.'''
    data = update.callback_query.data
    if data == '1':
        join(update, context)
    elif data == '2':
        quit(update, context)
    # CallbackQueries need to be answered, 
    # even if no notification to the user is needed
    # Some clients may have trouble otherwise.
    update.callback_query.answer()

def stop(update, context):
    '''Stop the game in progress.'''
    chatId = update.effective_chat.id
    players = tables[chatId] if chatId in tables else []
    if chatId not in phases or phases[chatId] == 0:
        stopText = 'No game started!'
    elif phases[chatId] == 1:   # phase of players joining, remove callback btns
        joinText = "Waiting for players to join ...\nJoined players:\n"
        joinText += '\n'.join([player.first_name for player in players])
        joinText += '\n(Game stopped)'
        joinMessages[chatId].edit_text(joinText)
        joinMessages[chatId] = None
        stopText = 'Game stopped.'
        players.clear()
        phases[chatId] = 0
        del joinMessages[chatId]
    else:   # further phases
        # TODO settle hands, tables, etc.
        stopText = 'Game stopped.'
        pass
    context.bot.send_message(
        chat_id=chatId, 
        text=stopText
    )

def error(update, context):
    '''Log Errors caused by Updates.'''
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def unknown(update, context):
    '''Reply to unrecognized commands. MUST be added LAST.'''
    context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Sorry, I didn't understand that command"
    )


if __name__ == '__main__':
    # register handlers in the dispatcher
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    #updater.dispatcher.add_error_handler(error)
    # unknown handler MUST be added after other handlers
    updater.dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    # start the bot
    updater.start_polling()
    # Run the bot until the user presses Ctrl-C or the process receives 
    # SIGINT, SIGTERM or SIGABRT
    updater.idle()
