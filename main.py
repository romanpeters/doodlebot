import os
import time
import datetime
import threading
import subprocess
from pprint import pprint
import telepot
from redacted import API_KEY
import doodle
import database as db


def chat(msg: dict):
    """on chat message"""
    content_type, chat_type, chat_id = telepot.glance(msg)
    user_to_db(user_id=msg['from']['id'], chat_id=chat_id, username=msg['from'].get('username'),
               first_name=msg['from'].get('first_name'), last_name=msg['from'].get('last_name'))
    if content_type == 'text':
        pprint(msg)
        if msg['text'].lower().startswith('/doodle'):
            command(msg)
            return

        urls = get_urls(msg)
        for url in urls:
            if 'doodle' in url:
                doodle_to_db(url, chat_id)
                bot.sendMessage(chat_id, "Doodle saved!")
                return


def get_urls(msg: dict) -> list:
    """Extract urls from msg"""
    urls = []
    entities = msg.get('entities')
    if not entities:
        return urls
    url_lengths = [l['length'] for l in entities if l['type'] == 'url']
    words = msg['text'].split()
    urls = [w for w in words if '.' in w and len(w) in url_lengths]
    return urls


def doodle_to_db(url: str, chat_id: int):
    """Add Doodle to db"""
    session = db.Session()
    entry = session.query(db.Doodle).filter_by(chat_id=chat_id).first()
    if entry:
        print(entry)
        if entry.url == url:
            session.close()
            return
        entry.url = url
    else:
        entry = db.Doodle(chat_id=chat_id, url=url)
    session.add(entry)
    session.commit()


def user_to_db(user_id, chat_id, username=None, first_name=None, last_name=None):
    session = db.Session()
    entry = db.User(user_id=user_id, username=username, first_name=first_name,
                    last_name=last_name)
    entry.chats.append(db.Chat(chat_id=chat_id))
    session.merge(entry)
    session.commit()


def command(msg):
    """Doodle that Doodle"""
    content_type, chat_type, chat_id = telepot.glance(msg)
    session = db.Session()
    doodle_entry = session.query(db.Doodle).filter_by(chat_id=chat_id).first()
    if not doodle_entry:
        bot.sendMessage(chat_id, "No doodle saved")
        return

    chat_entry = session.query(db.Chat).filter_by(chat_id=chat_id).first()
    users = chat_entry.users

    print(doodle_entry.url)
    print(users)
    for u in users:
        print(u.first_name)

    session.close()

    poll = doodle.Doodle(doodle_entry.url)

    # Check for poll
    if not poll.json_file:
        bot.sendMessage(chat_id, "Poll not found")
        return

    title = f"*{poll.get_title()}*"
    participants = "\n\U00002611".join(['']+poll.get_participants())

    # Check if poll is open
    if not poll.is_open():
        final_dates = [d[0].strftime('%A %d %B %H:%M') for d in poll.get_final()]
        bot.sendMessage(chat_id, "\n".join([title] + final_dates), parse_mode="Markdown")
        return

    bot.sendMessage(chat_id, f"{title}\n{participants}", parse_mode="Markdown")


if __name__ == '__main__':
    bot = telepot.Bot(API_KEY)
    bot.message_loop({'chat': chat})
    print('Listening...')
    while 1:
        time.sleep(10)