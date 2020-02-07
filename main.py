import os
import sys
import time
import datetime
import threading
import subprocess
from pprint import pprint
import telepot
from redacted import API_KEY
import database as db

sys.path.append("python-doodle")
import doodle

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


def levenshtein_distance(s1, s2):
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]


def identify(alias: str, users) -> int:
    """Get user id by alias"""
    alias = ''.join([c for c in alias.lower() if c.isalpha()])  # make lowercase and filter numbers
    names = []



    lowest = 100
    result = None
    for entry in aliases:
        ld = levenshteinDistance(entry.alias, alias)
        if ld == 0:
            return entry.id

        if ld < lowest:
            lowest = ld
            result = entry.id
    return result


# def get_missing(chat_entry, doodle_entry):
#     users = {u.user_id: [u.username, u.first_name, u.last_name] for u in chat_entry.users}
#
#
#     missing = [f"@{u.username}" for u in utils.get_missing(participants)]
#     poll_string = f"[{poll.get_title()}]({url}) ({len(participants)}/{len(whitelisted)})"
#     if poll.is_open():
#         additional_string = '\n'.join([u'\U00002611' + f" {p}" for p in participants] + [u'\U000025FB' + f" {m}" for m in missing])
#     else:
#         additional_string = f"Final date: {poll.get_final()[0].strftime('%A %d %B %H:%M')}"
#     bot.sendMessage(message.chat_id, '\n'.join([poll_string, additional_string]), parse_mode="Markdown",
#                     disable_web_page_preview=True)

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

    # print(doodle_entry.url)
    # print(users)
    # for u in users:
    #     print(u.first_name)

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
        final_dates = [d[0].strftime('%A %d %B %H:%M').replace("00:00", "") for d in poll.get_final()]
        bot.sendMessage(chat_id, "\n".join([title] + final_dates), parse_mode="Markdown")
        return

    bot.sendMessage(chat_id, f"{title}\n{participants}", parse_mode="Markdown")


if __name__ == '__main__':
    bot = telepot.Bot(API_KEY)
    bot.message_loop({'chat': chat})
    print('Listening...')
    while 1:
        time.sleep(10)