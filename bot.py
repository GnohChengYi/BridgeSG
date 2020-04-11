import os
from telegram.ext import CommandHandler, CallbackQueryHandler, Filters, \
    MessageHandler, Updater
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
from bridge import Game

# pass token with os config vars for security
token = os.environ['TELEGRAM_TOKEN']

# use_context=True for backward compatibility
updater = Updater(token=token, use_context=True)

# set up logging to know when and why things don't work as expected
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
    )
logger = logging.getLogger(__name__)

# game data
games = {} # TODO {chat_id:Game}, chat_id in games = game created, vice versa
joinMessages = {}   # messages waiting for players to join


# handlers and other helper functions
def get_markup():
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
            reply_markup=get_markup()
        )

def join(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = games[chatId]
    joinSuccess = game.addPlayer(user.id, user.first_name)
    if not joinSuccess:
        context.bot.send_message(
            chat_id=chatId,
            text = '{}, you already joined the game!'.format(user.first_name)
        )
    else:   # should be <4 players otw all btns should've been removed
        if not game.full():
            text = "Waiting for players to join ...\nJoined players:\n"
            text += '\n'.join([player.name for player in game.players])
            query.edit_message_text(text=text, reply_markup=get_markup())
        else:
            game.start()
            # TODO handle game begun
            text = "Joined players:\n"
            text += '\n'.join([player.name for player in game.players])
            text += '\nGame has begun! Check your PMs to see your hands.'
            query.edit_message_text(text=text)

def quit(update, context):
    chatId = update.effective_chat.id
    query = update.callback_query
    user = query.from_user
    game = games[chatId]
    quitSuccess = game.delPlayer(user.id, user.first_name)
    if not quitSuccess:
        context.bot.send_message(
            chat_id=chatId,
            text = '{}, you haven\'t joined the game!'.format(user.first_name)
        )
    else:
        text = "Waiting for players to join ...\nJoined players:\n"
        text += '\n'.join([player.first_name for player in game.players])
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
        joinText += '\n'.join([player.first_name for player in game.players])
        joinText += '\n(Game stopped)'
        joinMessages[chatId].edit_text(joinText)
    context.bot.send_message(
        chat_id=chatId, 
        text='Game stopped.'
    )
    del games[chatId]
    del joinMessages[chatId]

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
