#!/usr/bin/env python3

import traceback
import urllib.error
import urllib.request
from ilswbot.config import TELEGRAM_API_KEY, API_URL
from ilswbot.db import get_session
from ilswbot.subscriber import Subscriber

from telegram.ext import (
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)


class Ilsw():
    """A bot which checks if Lukas is already awake.

    If Lukas isn't awake, we notify everybody who asked,
    as soon as he wakes up!. Critical importance!!!
    """
    def __init__(self):
        """Initialize telegram bot and all needed variables."""
        self.last_status = None
        self.subscribers = []
        self.updater = Updater(token=TELEGRAM_API_KEY)

        # Add reoccurring jobs
        job_queue = self.updater.job_queue
        job_queue.run_repeating(self.answer_subscribers, interval=60, first=0)

        # Create handler
        message_handler = MessageHandler(Filters.text, self.process)
        stop_handler = CommandHandler('stop', self.stop)
        start_handler = CommandHandler('start', self.start)

        # Add handler
        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(message_handler)
        dispatcher.add_handler(stop_handler)
        dispatcher.add_handler(start_handler)

        # Start to poll messages
        self.updater.start_polling()

    def main(self):
        """The main loop of the bot."""
        self.updater.idle()

    def start(self, bot, update):
        """Start the bot."""
        try:
            session = get_session()
            chat_id = update.message.chat_id
            subscriber = self.get_or_create_subscriber(session, chat_id)

            subscriber.active = True
            session.add(subscriber)
            session.commit()
            session.close()

            text = "I'm spying on Lukas :3"
            bot.sendMessage(chat_id=chat_id, text=text)
        except Exception as e:
            print(traceback.format_exc())
            raise

    def stop(self, bot, update):
        """Stop the bot."""
        try:
            session = get_session()
            chat_id = update.message.chat_id

            subscriber = self.get_or_create_subscriber(session, chat_id)
            subscriber.active = False
            session.add(subscriber)
            session.commit()
            session.close()

            text = "Stopped spying on Lukas :("
            bot.sendMessage(chat_id=chat_id, text=text)
        except Exception as e:
            print(traceback.format_exc())
            raise

    def process(self, bot, update):
        """Check if anybody asked for lukas's status and anser them."""
        try:
            session = get_session()
            message = update.message.text.lower()
            chat_id = update.message.chat_id
            subscriber = self.get_or_create_subscriber(session, chat_id)
            if subscriber.active is False:
                return

            # Flame Lukas, if he asks for his own sleep status. Subscribing is allowed
            if 'lukasovich' == update.message.from_user.username.lower():
                if 'wach' in message:
                    bot.sendMessage(chat_id=update.message.chat_id, text='Halt die Fresse Lukas >:S')
                    return

            # Lukas mentioned and wach in one sentence.
            lukas_names = ['lukas', 'lulu']
            if len(list(filter(lambda name: name in message, lukas_names))) > 0 and 'wach' in message:

                success, response = self.get_lukas_status()
                if success and response == 'NEIN':
                    subscriber.waiting = True
                    session.add(subscriber)
                    session.commit()
                bot.sendMessage(chat_id=chat_id, text=response)
        except Exception as e:
            print(traceback.format_exc())
            raise

    def get_lukas_status(self):
        """Poll the ilsw api for lukas's sleep status."""
        try:
            status = urllib.request.urlopen(API_URL).read()
            return True, status.decode('utf-8')
        except urllib.error.HTTPError:
            return False, 'Jo. Die Api ist im Sack.'

    def answer_subscribers(self, bot, job):
        """Check if Lukas is now awake and notify everybody who asked, while he was sleeping."""
        try:
            session = get_session()
            subscriber = session.query(Subscriber) \
                .filter(Subscriber.waiting == True) \
                .all()
            if len(self.subscribers) != 0:
                return

            success, api_response = self.get_lukas_status()
            if success and api_response != 'JA':
                return
            for subscriber in self.subscribers:
                response = "Leute, Lukas is grad aufgewacht!"
                bot.sendMessage(chat_id=subscriber, text=response)

        except Exception as e:
            print(traceback.format_exc())
            raise

    def get_or_create_subscriber(self, session, chat_id):
        """Get or create a new subscriber."""
        subscriber = session.query(Subscriber).get(chat_id)
        if not subscriber:
            subscriber = Subscriber(chat_id)
            session.add(subscriber)
            session.commit()
            subscriber = session.query(Subscriber).get(chat_id)

        return subscriber
