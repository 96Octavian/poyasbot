#!/usr/bin/env python3.7

# TODO: Rewrite sudoku solver
# TODO: Rework anything GDPR related
# TODO: Comments
# TODO: Pydocs maybe
# TODO: Better and consistent logging

import logging
from requests import get
import threading
import emoji
import sys
import time
import string
import json
import datetime
import random
import re
from signal import SIGTERM
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, Filters, CallbackQueryHandler, MessageHandler)


"""
Boya Telegram bot
"""

# Enable logging
logger = logging.getLogger("Boya")
logger.setLevel(logging.INFO)

try:
    from systemd.journal import JournaldLogHandler as JournalHandler

    log_fmt = logging.Formatter('%(levelname)s: %(message)s')
    log_ch = JournalHandler(identifier='Boya')
    log_ch.setFormatter(log_fmt)
    logger.addHandler(log_ch)
except ImportError:
    pass


# Log chat messages
def log_on_chat_message(update, context):
    from_id = str(update.message.from_user.id)
    chat_id = str(update.message.chat.id)
    logger.debug(f'Chat message from {from_id} ({chat_id})')


# Log callback queries
def log_on_callback_query(update, context):
    query = update.callback_query
    data = query.data
    logger.debug(f'Callback query: {query.id} {query.from_user.id} {data}')


# Maintain a contacts list
def contacts_logger(update, context):
    if update.message.chat.type == "channel":
        context.bot.sendMessage(ADMIN, "Channel message received")
        return

    from_id = str(update.message.from_user.id)
    chat_id = str(update.message.chat.id)
    first_name = str(update.message.from_user.first_name)
    last_name = str(update.message.from_user.last_name)
    username = str(update.message.from_user.username)

    if from_id not in files.contacts:
        files.contacts[from_id] = {}
        files.contacts[from_id]['first_name'] = []
        files.contacts[from_id]['last_name'] = []
        files.contacts[from_id]['username'] = []

    if first_name not in files.contacts[from_id]['first_name']:
        files.contacts[from_id]['first_name'].append(first_name)
    if username not in files.contacts[from_id]['username']:
        files.contacts[from_id]['username'].append(username)
    if last_name is not None and last_name not in files.contacts[from_id]['last_name']:
        files.contacts[from_id]['last_name'].append(last_name)

    if update.message.chat.type == "group" or update.message.chat.type == "supergroup":
        group_title = str(update.message.chat.title)
        if chat_id not in files.contacts:
            files.contacts[chat_id] = {}
            files.contacts[chat_id]['group_title'] = set()
        if from_id not in files.contacts[chat_id]:
            files.contacts[chat_id][from_id] = {}
            files.contacts[chat_id][from_id]['first_name'] = set()
            files.contacts[chat_id][from_id]['last_name'] = set()
            files.contacts[chat_id][from_id]['username'] = set()

        files.contacts[chat_id]['group_title'].append(group_title)
        if first_name not in files.contacts[chat_id][from_id]['first_name']:
            files.contacts[chat_id][from_id]['first_name'].append(first_name)
        if username not in files.contacts[chat_id][from_id]['username']:
            files.contacts[chat_id][from_id]['username'].append(username)
        if last_name is not None and last_name not in files.contacts[chat_id][from_id]['last_name']:
            files.contacts[chat_id][from_id]['last_name'].append(last_name)

    files.modified_files.append((files.contacts, "contacts"))


# Callback queries for challenge
def on_callback_challenge(update, context):
    query = update.callback_query
    data = query.data
    logger.debug(f'Callback query: {query.id} {query.from_user.id} {data}')

    player = str(query.from_user.id)
    if player not in files.score.keys():
        files.score[player] = 0

    keyboard = [[InlineKeyboardButton("Done", callback_data='challenge_done'),
                 InlineKeyboardButton("Back", callback_data='challenge_back')],
                [InlineKeyboardButton("Reset", callback_data='challenge_reset')]]
    reply_keyboard = InlineKeyboardMarkup(keyboard)

    if data == 'challenge_done':
        if files.score[player] < len(files.challenge) - 1:
            files.score[player] += 1
            files.modified_files.append((files.score, "score"))
            query.answer(text="Next challenge")
        else:
            query.answer(text="Victory!")

    elif query.data == 'challenge_back':
        if files.score[player] > 0:
            files.score[player] -= 1
            files.modified_files.append((files.score, "score"))
        query.answer(text="Meh...")

    elif query.data == 'challenge_reset':
        if files.score[player] != 0:
            files.score[player] = 0
            files.modified_files.append((files.score, "score"))
        query.answer(text='Weakness disgusts me')

    query.edit_message_text(files.challenge[files.score[player]],
                            reply_markup=reply_keyboard, quote=False, parse_mode='HTML')


# Check if it is me
def authorized(update):
    return str(update.message.chat.id) == ADMIN


# Callback queries for pepe the frog
def on_callback_pepe(update, context):
    query = update.callback_query
    data = query.data
    logger.debug(f'Callback query: {query.id} {query.from_user.id} {data}')

    if data == 'pepe_alert':
        query.answer(text='Here come dat boi!!', show_alert=True)
        th = threading.Timer(random.randint(30, 300),
                             lambda contxt, qery: contxt.bot.sendAudio(qery.message.chat.id,
                                                                       u'CQADBAADegEAAjhP8FEnoDBo_8Lc4QI'),
                             args=([context, query]))
        th.start()
    elif data == 'pepe_frog':
        context.bot.sendPhoto(query.message.chat.id, u'AgADBAADfakxGzDP9QNSBGjGQA24skByWBkABMe42H0v2kaTinUAAgI')
        query.answer(text='Sad Pepe')
    elif data == 'pepe_edit':
        lenny_face = u'( \u0361\xb0 \u035c\u0296 \u0361\xb0)'
        query.edit_message_text(lenny_face, reply_markup=None)


# Thread subclass to send messages for stories
class Story(threading.Thread):
    def __init__(self, update, name):
        self.stopped = False
        self.update = update
        threading.Thread.__init__(self, name=name)

    def stop(self):
        self.stopped = True

    def run(self):
        story = random.choice(files.stories)
        logger.info("Started telling a Story...")
        for e in story:
            if self.stopped:
                break
            self.update.message.reply_text(emoji.emojize(e, use_aliases=True), parse_mode='HTML', quote=False)
            time.sleep(random.randint(1, 15))
        logger.info("Storytelling is over")
        return


# Search text messages for any match
def quoter(update):
    text_low = update.message.text.lower()
    text_low = text_low.translate(str.maketrans("", "", string.punctuation))
    list_low = text_low.split()
    if 'dat boi' in text_low:
        keyboard = [[InlineKeyboardButton("dat boi", callback_data='pepe_edit'),
                     InlineKeyboardButton("That frog", callback_data='pepe_frog')],
                    [InlineKeyboardButton("shit waddup", callback_data='pepe_alert')]]
        datboi_markup = InlineKeyboardMarkup(keyboard)

        update.message.reply_text("Who's coming?", reply_markup=datboi_markup, quote=False)

        logger.debug("Found dat boi")
        return
    if re.match("(.*)smett(.*)di raccontare", text_low):
        no_story = True
        for thread in threading.enumerate():
            if thread.is_alive() and thread.getName() == str(update.message.chat.id):
                no_story = False
                thread.stop()
                update.message.reply_text("D'accordo adesso la smetto...", quote=False)
                break
        if no_story:
            update.message.reply_text("Ma se non sto parlando!", quote=False)
    if re.match("(.*)raccont(.*)storia", text_low, re.M):
        can_start = True
        for thread in threading.enumerate():
            if thread.is_alive() and thread.getName() == str(update.message.chat.id):
                can_start = False
                update.message.reply_text("Sto parlando lasciami finire", quote=False)
                break
        if can_start:
            Story(update, str(update.message.chat.id)).start()
    if text_low in files.exact_quote:
        update.message.reply_text(files.exact_quote[text_low], parse_mode='HTML', quote=False)
        logger.debug("Found exact quote")
        return
    if 'gay' in text_low or 'ebrei' in text_low or 'ebreo' in text_low:
        update.message.reply_text(f'{update.message.from_user.first_name} gay capo degli ebrei', quote=False)
        logger.debug("Found quote")
    for key in files.sticker:
        if key in text_low:
            update.message.reply_sticker(random.choice(files.sticker[key]))
            logger.debug("Found sticker quote")
    for key in files.parsed_long_quote:
        if key in text_low:
            update.message.reply_text(files.parsed_long_quote[key], parse_mode='HTML', quote=False)
            logger.debug("Found parsed long quote")
    for word in set(list_low):
        if word in files.parsed_quote:
            update.message.reply_text(files.parsed_quote[word], parse_mode='HTML', quote=False)
            logger.debug("Found parsed quote")
    for key in files.parsed_audio:
        if key in text_low:
            update.message.reply_audio(random.choice(files.parsed_audio[key]))
            logger.debug("Found audio")
    for key in files.voice:
        if key in text_low:
            update.message.reply_voice(random.choice(files.voice[key]))
            logger.debug("Found voice")


# Send time
def command_time(update, context):
    logger.debug("Found command \'/time\'")
    update.message.reply_text(str(datetime.datetime.now()), quote=False)


# Send ip only to admin
def command_ip(update, context):
    logger.debug("Found command \'/ip\'")
    if not authorized(update):
        update.message.reply_text('Fatti gli affari tuoi')
        logger.warning(f'User {update.message.from_user.id} asked for your IP address')
    else:
        my_ip = get('https://ipapi.co/ip/').text
        update.message.reply_text(my_ip, quote=False)


# Magic 8-ball but with Helix
def command_askhelix(update, context):
    logger.debug('Found command "/askhelix"')
    if len(context.args) > 0:
        update.message.reply_photo(photo=u'AgADBAADP6kxG5F4IFHzHNogHd2gH9stqRkABI-koNF65li5BLsBAAEC', quote=False)
        update.message.reply_text(text=f'<code>The all-wise Fossil says:</code>\n{random.choice(files.helixAnswers)}',
                                  parse_mode='HTML')
    else:
        update.message.reply_photo(photo=u'AgADBAADP6kxG5F4IFHzHNogHd2gH9stqRkABI-koNF65li5BLsBAAEC', quote=False)
        update.message.reply_text(text="<code>No questions were asked</code>", parse_mode='HTML')


# Blue whale challenge engineering style
def command_challenge(update, context):
    logger.debug('Found command "/challenge"')
    player = str(update.message.from_user.id)
    keyboard = [[InlineKeyboardButton("Done", callback_data='challenge_done'),
                 InlineKeyboardButton("Back", callback_data='challenge_back')],
                [InlineKeyboardButton("Reset", callback_data='challenge_reset')]]
    reply_keyboard = InlineKeyboardMarkup(keyboard)

    if player not in files.score.keys():
        files.score[player] = 0
        files.modified_files.append((files.score, "score"))
    update.message.reply_text(files.challenge[files.score[player]],
                              reply_markup=reply_keyboard,
                              parse_mode='HTML', quote=False)


# Receive every text message
def on_chat_message(update, context):
    quoter(update)


# Log errors
def error_logger(update, context):
    """Log Errors caused by Updates."""
    logger.warning(f'Update "{update}" caused error "{context.error}"')


# Add a trigger to a message containing some word/sentence
def command_add(update, context):
    logger.info('Found command "/add"')
    command = update.message.text.replace("/add", '').strip()
    if len(command) < 3:
        update.message.reply_text('Sintassi errata.\nProva "/add <code>citazione</code>"',
                                  parse_mode='HTML', quote=False)
        return
    command = command.split("@.")
    trig = command[0].lower().strip().translate(str.maketrans("", "", string.punctuation))
    if trig in files.parsed_quote or trig in files.parsed_long_quote:
        update.message.reply_text('Che pervy', quote=False)
        update.message.reply_text(emoji.emojize(':thumbs_up_sign:', use_aliases=True), quote=False)
        return
    admin_msg = f'{update.message.from_user.id} added {trig}'
    answer = 'Ahahahahah'
    if len(command) == 2:
        answer = command[1].strip()
        admin_msg = f'{admin_msg}: {answer}'
    if ' ' in trig:
        files.parsed_long_quote[trig] = answer
        files.modified_files.append((files.parsed_long_quote, "parsed_long_quote"))
    else:
        files.parsed_quote[trig] = answer
        files.modified_files.append((files.parsed_quote, "parsed_quote"))
    context.bot.sendMessage(ADMIN, admin_msg)
    update.message.reply_text('Che divertente', quote=False)
    logger.info(f'Added \'{trig}\'')


# Add a trigger to an exact message
def command_addtodict(update, context):
    logger.info('Found command "/addtodict"')
    command = update.message.text.replace("/addtodict", "").strip()
    try:
        trig, answer = command.split("@.")
        trig = trig.lower().strip().translate(str.maketrans("", "", string.punctuation))
        answer = answer.strip()
        if trig in files.exact_quote:
            update.message.reply_text("C\'era gi\u00e0", quote=False)
            return
        else:
            files.exact_quote[trig] = answer
            context.bot.sendMessage(ADMIN, f'{update.message.from_user.id} added {trig}: {answer}')
            update.message.reply_text("Caaaaaan do", quote=False)
        files.modified_files.append((files.exact_quote, "exact_quote"))
        logger.info(f'Added \'{trig}\'')

    except ValueError:
        update.message.reply_text(
            'Sintassi errata.\nProva "/addtodict <code>citazione</code> + @. + <code>risposta</code>"',
            quote=False)


# Delete a trigger
def command_del(update, context):
    logger.info('Received command "/del"')
    if not authorized(update):
        update.message.reply_text('Come ti permetti', quote=False)
        return

    trig = update.message.text.replace("/del", "").strip().lower().translate(str.maketrans("", "", string.punctuation))

    if files.parsed_quote.pop(trig, None) is not None:
        update.message.reply_text('Eliminata', quote=False)
        files.modified_files.append((files.parsed_quote, "parsed_quote"))
        logger.info(f'Removed "{trig}"')
    elif files.parsed_long_quote.pop(trig, None) is not None:
        update.message.reply_text('Eliminata', quote=False)
        files.modified_files.append((files.parsed_long_quote, "parsed_long_quote"))
        logger.info(f'Removed "{trig}"')
    else:
        update.message.reply_text("Guarda che non c'era", quote=False)


# Delete an exact trigger
def command_delfromdict(update, context):
    logger.info('Received command "/delfromdict"')
    if not authorized(update):
        update.message.reply_text('Come ti permetti', quote=False)
        return
    trig = update.message.text.replace("/delfromdict", "").strip().lower().translate(
        str.maketrans("", "", string.punctuation))
    if files.exact_quote.pop(trig, None) is not None:
        update.message.reply_text('Eliminata', quote=False)
        files.modified_files.append((files.exact_quote, "exact_quote"))
        logger.info(f'Removed "{trig}"')
    else:
        update.message.reply_text("Guarda che non c'era", quote=False)


# Show bot instructions
def command_help(update, context):
    update.message.reply_text(
        "/time\n"
        "/askhelix + yes or no question\n"
        "/challenge\n"
        "/addtodict + citazione @. risposta\n"
        "/add + citazione\n"
        "/add + citazione @. risposta\n"
        "/del + citazione\n"
        "/delfromdict + citazione\n"
    )


def signal_handler(signum, frame):
    logger.info(f'Received signal {signum}')

    if signum == SIGTERM:
        files.write_all()


def main():
    # Handlers groups to better control message flow
    LOGGING, PREPROCESS, NORMAL = 1, 2, 3

    # Create the Updater and pass it your bot's token.
    updater = Updater(sys.argv[1], user_sig_handler=signal_handler, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.add_handler(CallbackQueryHandler(log_on_callback_query), group=LOGGING)
    dp.add_handler(MessageHandler(Filters.all, log_on_chat_message), group=LOGGING)

    # All messages
    dp.add_handler(MessageHandler(Filters.all, contacts_logger), group=PREPROCESS)

    # On different commands
    dp.add_handler(CommandHandler("time", command_time))
    dp.add_handler(CommandHandler("ip", command_ip, Filters.private))
    dp.add_handler(CommandHandler("askhelix", command_askhelix))
    dp.add_handler(CommandHandler("challenge", command_challenge))
    dp.add_handler(CommandHandler("add", command_add, Filters.private))
    dp.add_handler(CommandHandler("addtodict", command_addtodict, Filters.private))
    dp.add_handler(CommandHandler("del", command_del, Filters.private))
    dp.add_handler(CommandHandler("delfromdict", command_delfromdict, Filters.private))
    dp.add_handler(CommandHandler("help", command_help))

    # On text messages without a command
    dp.add_handler(MessageHandler(Filters.text, on_chat_message), group=NORMAL)

    # Callback queries
    dp.add_handler(CallbackQueryHandler(on_callback_challenge, pattern='^challenge_'))
    dp.add_handler(CallbackQueryHandler(on_callback_pepe, pattern='^pepe_'))

    # log all errors
    dp.add_error_handler(error_logger)

    # Start the Bot
    updater.start_polling()

    updater.bot.sendMessage(ADMIN, "Bot started")
    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

    logger.warning("Shutting down...")
    return


# Open all the useful files at once
class FilesContainer:

    def __init__(self):
        self.modified_files = []
        self.lock = threading.Lock()
        self.helixAnswers = []
        self.challenge = []
        self.score = {}
        self.exact_quote = {}
        self.parsed_quote = {}
        self.parsed_long_quote = {}
        self.contacts = {}
        self.parsed_audio = {}
        self.sticker = {}
        self.voice = {}
        self.stories = {}
        self.load_all()
        self.periodic_save = threading.Timer(7200, self.write_all)
        self.periodic_save.start()

    # Load all files
    def load_all(self):
        self.lock.acquire()

        try:
            with open("./files/helix_answers.lst", "r", encoding='utf-8') as file:
                self.helixAnswers = [line.strip() for line in file]
        except IOError:
            pass
        try:
            with open('./files/challenge.lst', 'r', encoding='utf-8') as file:
                self.challenge = [line.strip() for line in file]
        except IOError:
            pass
        try:
            with open('./files/score.json', 'r', encoding='utf-8') as file:
                self.score = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/exact_quote.json', 'r', encoding='utf-8') as file:
                self.exact_quote = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/parsed_quote.json', 'r', encoding='utf-8') as file:
                self.parsed_quote = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/parsed_long_quote.json', 'r', encoding='utf-8') as file:
                self.parsed_long_quote = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/contacts.json', 'r', encoding='utf-8') as file:
                self.contacts = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/parsed_audio.json', 'r', encoding='utf-8') as file:
                self.parsed_audio = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/sticker.json', 'r', encoding='utf-8') as file:
                self.sticker = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/voice.json', 'r', encoding='utf-8') as file:
                self.voice = json.load(file)
        except IOError:
            pass
        try:
            with open('./files/stories.json', 'r', encoding='utf-8') as file:
                stories_dict = json.load(file)
                self.stories = stories_dict['base']
        except IOError:
            pass
        self.lock.release()

        logger.debug("All files opened")

    # Write out all the modified files
    def write_all(self):
        file_number = len(self.modified_files)

        for file in self.modified_files:
            self.store(file)
        self.modified_files = []

        logger.debug(f'Saved {file_number} files')

    # To be called whenever a file is modified
    # spec is a tuple (file, filename)
    def store(self, spec):
        self.lock.acquire()
        with open(f'./files/{spec[1]}.json', 'w') as json_file:
            json.dump(spec[0], json_file, sort_keys=True, indent=4, separators=(',', ': '))
        self.lock.release()
        logger.debug(f'Updated file {spec[1]}.json')


if __name__ == '__main__':
    ADMIN = sys.argv[2]
    files = FilesContainer()

    logger.info(f'Files loaded, admin: {ADMIN}')
    main()
    files.periodic_save.cancel()
