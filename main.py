import sys
import time
from pprint import pprint
import telepot
from redacted import API_KEY
import database as db

sys.path.append("python-doodle")  # python-doodle is located in a git submodule
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
    poll = doodle.Doodle(doodle_entry.url)
    message = DoodleMessage(poll=poll, chat_entry=chat_entry).get_message()

    session.close()

    bot.sendMessage(chat_id, message, parse_mode="Markdown", disable_web_page_preview=True)


class DoodleMessage(object):
    def __init__(self, poll, chat_entry):
        self.poll: doodle.Doodle = poll
        self.chat_entry: db.Chat = chat_entry
        self.chat_members = {u.user_id: u for u in chat_entry.users}
        self.title: str = f"*{poll.get_title()}*"
        self.participants: str = "\n\U00002611".join([''] + poll.get_participants()).strip()
        self.final_dates: str = str([d[0].strftime('%A %d %B %H:%M').replace("00:00", "") for d in poll.get_final()])
        self.missing: str = "\n\U000025FB".join([''] + self.get_missing()).strip()

    def get_message(self):
        if not self.poll.is_open():
            return "\n".join([self.title, self.final_dates])
        return f"{self.title}\n{self.poll.url}\n{self.participants}\n{self.missing}"

    def get_missing(self) -> list:
        """lists chat_members who did not participate in the doodle"""
        chat_members = self.chat_members.copy()
        participating = self.poll.get_participants()
        for doodler in participating:
            chat_id = self.identify(doodler)
            try:
                chat_members.pop(chat_id)
            except KeyError:
                pass
        names = []
        for user in chat_members.values():
            names.append(f"@{user.username}" if user.username else user.first_name)
        return names

    def identify(self, name) -> int:
        """Returns the chat_id of a user"""
        score = float("inf")
        most_likely = None
        for chat_id, user in self.chat_members.items():
            user_names = [user.username, user.first_name, user.last_name, f"{user.first_name} {user.last_name}"]
            for user_name in user_names:
                edit_distance = self.levenshtein(name, user_name)
                if edit_distance == 0:  # perfect match
                    return chat_id
                if edit_distance < score:
                    score = edit_distance
                    most_likely = chat_id
        return most_likely

    def levenshtein(self, a, b):
        s1, s2 = a.lower(), b.lower()
        if len(s1) > len(s2):
            s1, s2 = s2, s1

        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_
        return distances[-1]









if __name__ == '__main__':
    bot = telepot.Bot(API_KEY)
    bot.message_loop({'chat': chat})
    print('Listening...')
    while 1:
        time.sleep(10)