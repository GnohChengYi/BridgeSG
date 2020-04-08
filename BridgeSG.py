from telegram.ext import CommandHandler, CallbackQueryHandler, Filters, \
    MessageHandler, Updater
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# TODO remove token if share code online, otw other ppl can control my bot
token = '1026774742:AAFkgzlK3KcyGt8XLzBxu33fqvfdQ-BpaQc'

# use_context=True for backward compatibility
updater = Updater(token=token, use_context=True)

# set up logging to know when and why things don't work as expected
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
    )
logger = logging.getLogger(__name__)

# game details
# TODO check gamePhase: 0=none, 1=join, 2=bid, 3=play
gamePhase = 0
players = []
joinMessage = None  # message waiting for players to join


# handlers and other helper functions
def get_markup(join=True, quit=True, addBot=True, delBot=True):
    '''Get a keyboard with the given buttons.'''
    firstRow, secondRow = [], []
    if join:
        firstRow.append(InlineKeyboardButton("Join!", callback_data='1'))
    if quit:
        firstRow.append(InlineKeyboardButton("Quit...", callback_data='2'))
    if addBot:
        secondRow.append(InlineKeyboardButton("Add bot", callback_data='3'))
    if delBot:
        secondRow.append(InlineKeyboardButton("Delete bot", callback_data='4'))
    return InlineKeyboardMarkup([firstRow, secondRow])

def start(update, context):
    global gamePhase, joinMessage
    if gamePhase > 0:
        context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="A game has already started!"
        )
    elif gamePhase == 0:
        gamePhase = 1
        joinMessage = context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="Waiting for players to join ...\nJoined players:",
            reply_markup=get_markup()
        )
    else:
        raise Exception('gamePhase  not number  or  < 0')

def join(update, context):
    query = update.callback_query
    user = query.from_user
    if user in players:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text = '{}, you already joined the game!'.format(user.first_name)
        )
    else:   # should be <4 players otw join btn should've been removed
        players.append(user)
        text = "Waiting for players to join ...\nJoined players:\n"
        text += '\n'.join([player.first_name for player in players])
        if len(players) < 4:
            markup = get_markup()
        else:   # no join btn when there are 4 players
            markup = get_markup(join=False)
        query.edit_message_text(text=text, reply_markup=markup)

def button(update, context):
    '''Pass the query to respective handlers.'''
    data = update.callback_query.data
    if data == '1':
        join(update, context)
    # CallbackQueries need to be answered, 
    # even if no notification to the user is needed
    # Some clients may have trouble otherwise.
    update.callback_query.answer()

def stop(update, context):
    '''Stop the game in progress.'''
    global gamePhase, joinMessage
    gamePhase = 0
    if joinMessage is not None:
        joinText = "Waiting for players to join ...\nJoined players:\n"
        joinText += '\n'.join([player.first_name for player in players])
        joinText += '\n(Game stopped)'
        joinMessage.edit_text(joinText)
        joinMessage = None
        stopText = 'Game stopped.'
        players.clear()
    else:
        stopText = 'No game started!'
    context.bot.send_message(
        chat_id=update.effective_chat.id, 
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
