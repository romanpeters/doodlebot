import sys
import os
import time
from pprint import pprint
import telepot
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from redacted import BOT_TOKEN
import database as db

sys.path.append("python-doodle")  # python-doodle is located in a git submodule
import doodle

show_calendar_link = True
if show_calendar_link:
    import dropbox
    from dropbox.exceptions import ApiError
    import icalendar
    from redacted import DROPBOX_TOKEN


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


def doodle_to_db(url: str, chat_id: int, ical_url: str = None):
    """Add Doodle to db"""
    session = db.Session()
    entry = session.query(db.Doodle).filter_by(chat_id=chat_id).first()
    if entry:
        entry.url = url
        if ical_url:
            entry.ical_url = ical_url
    else:
        entry = db.Doodle(chat_id=chat_id, url=url, ical_url=ical_url)
    session.add(entry)
    session.commit()


def user_to_db(user_id, chat_id, username=None, first_name=None, last_name=None):
    session = db.Session()
    entry = db.User(user_id=user_id, username=username, first_name=first_name,
                    last_name=last_name)
    entry.chats.append(db.Chat(chat_id=chat_id))
    session.merge(entry)
    session.commit()


def get_ical_url_from_db(chat_id: int) -> str:
    session = db.Session()
    doodle_entry = session.query(db.Doodle).filter_by(chat_id=chat_id).first()
    session.close()
    if doodle_entry.ical_url:
        return doodle_entry.ical_url
    return ""


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

    reply_markup = None
    if not poll.is_open():
        if show_calendar_link:
            ical_url = get_ical_url_from_db(chat_id=chat_id)
            if not ical_url:
                ical_url = DropBoxUploader(poll).get_url()
                doodle_to_db(url=doodle_entry.url, chat_id=doodle_entry.chat_id, ical_url=ical_url)

            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [dict(text='Add to calendar', url=ical_url)]
            ])
    bot.sendMessage(chat_id, message, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=reply_markup)
    session.close()

class DropBoxUploader(object):
    dbx = dropbox.Dropbox(DROPBOX_TOKEN)

    def __init__(self, poll):
        assert not poll.is_open()
        self.event_times = poll.get_final()
        self.title = poll.get_title()
        self.location = poll.get_location()
        self.dropbox_folder = "/doodlebot/"
        self.filename = f".{int(time.time())}.ics"
        self.dropbox_path = self.dropbox_folder+self.filename[1:]
        self.dl_url = ""
        self.direct_dl_url = ""

        self.upload()


    def create_ical(self):
        cal = icalendar.Calendar()
        for start_end in self.event_times:
            event = icalendar.Event()
            event.add('summary', self.title)
            event.add('dtstart', start_end[0])
            event.add('dtend', start_end[1])
            event.add('location', self.location)
            cal.add_component(event)
        return cal.to_ical()

    def upload(self):
        with open(self.filename, "wb+") as f:
            f.write(self.create_ical())

        with open(self.filename, 'rb') as f:
            self.dbx.files_upload(f.read(), path=self.dropbox_path)

        # remove original file
        os.remove(self.filename)

    def get_url(self):
        try:
            self.dl_url = self.dbx.sharing_create_shared_link_with_settings(self.dropbox_path).url
        except ApiError as e:
            error_string = str(e)
            url_and_more = error_string.split('https://')[1]
            self.dl_url = 'https://' + url_and_more.split("',")[0]
        self.direct_dl_url = self.dl_url.replace('?dl=0', '?dl=1')
        return self.direct_dl_url



class DoodleMessage(object):
    def __init__(self, poll, chat_entry, ical_url=None):
        self.poll: doodle.Doodle = poll
        self.chat_entry: db.Chat = chat_entry
        self.ical_url = ical_url
        self.chat_members = {u.user_id: u for u in chat_entry.users}
        self.title: str = f"*{poll.get_title()}*"
        self.participants: str = "\n\U00002611".join([''] + poll.get_participants()).strip()
        self.final_dates: str = '\n'.join([d[0].strftime('%A %d %B %H:%M').replace("00:00", "") for d in poll.get_final()])
        self.missing: str = "\n\U00002610".join([''] + self.get_missing()).strip()


    def get_message(self):
        if not self.poll.is_open():
            lines = [self.title]
            if self.ical_url:
                lines.append(f"[add to calendar]({self.ical_url})")
            lines.append(self.final_dates)
            return "\n".join(lines)
        return f"{self.title}\n{self.poll.url}\n{self.participants}\n{self.missing}"

    def get_missing(self) -> list:
        """lists chat_members who did not participate in the doodle"""
        chat_members = self.chat_members.copy()
        participating = self.poll.get_participants()

        print("chat_members:")
        for chat_id, u in chat_members.items():
            print(u.first_name)

        for doodler in participating:
            chat_id = self.identify(doodler)
            try:
                chat_members.pop(chat_id)
            except KeyError:
                pass
        names = []
        for user in chat_members.values():
            mention_name = f"@{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.user_id})"
            names.append(mention_name)
        return names

    def identify(self, name) -> int:
        """Returns the chat_id of a user"""
        score = float("inf")
        most_likely = None
        for chat_id, user in self.chat_members.items():                    # Check name against different aliases
            user_names = [user.first_name]                                 # john
            if user.username:
                user_names.append(user.username)                           # @johndoe
            if user.last_name:
                user_names.extend([user.last_name,                         # doe
                                  user.first_name + user.last_name,        # johndoe
                                  user.first_name[0] + user.last_name,     # jdoe
                                  user.first_name + user.last_name[0]])    # johnd
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
    bot = telepot.Bot(BOT_TOKEN)
    bot.message_loop({'chat': chat})
    print('Listening...')
    while 1:
        time.sleep(10)
