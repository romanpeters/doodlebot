"""
Python wrapper for the Doodle API
GET, no POST
"""
import requests
import json
import datetime
import urllib.parse


class Doodle:
    """Connect with WieBetaaltWat"""
    # no idea if tz_offset is always 13 hours, y.m.m.v.
    tz_offset = 46800  # seconds

    def __init__(self, url=None, poll_id=None):
        assert url or poll_id
        if not poll_id:
            parsed = urllib.parse.urlparse(url)
            poll_id = parsed.path.replace('/','').replace('poll','')
        self.base_url = f"https://doodle.com/api/v2.0/polls/{poll_id}?adminKey=&participantKey="
        self.json_file = None
        self.update()

    def update(self, url: str=None):
        """Send a request to Doodle"""
        if not url:
            url=self.base_url
        req = requests.request('get', url)
        if req.status_code == 200:
            self.json_file = json.loads(req.text)
        elif req.status_code == 404:
            return
        else:
            print(url)
            print(req.status_code)
            print(req.text)
            raise ConnectionError

    def get_participants(self) -> list:
        return [p['name'] for p in self.json_file["participants"]]

    def get_title(self) -> str:
        return self.json_file['title']

    def get_location(self) -> str or None:
        location = self.json_file.get('location')
        if location:
            return location['name']

    def get_description(self) -> str or None:
        return self.json_file.get('description')

    def get_comments(self) -> list:
        return self.json_file.get('comments')

    def get_initiator(self) -> str:
        return self.json_file["initiator"][0]['name']

    def get_latest_change(self) -> datetime:
        return datetime.datetime.fromtimestamp(self.json_file["latestChange"]/1000 - self.tz_offset)

    def get_final(self) -> list:
        options = self.json_file.get('options')
        if options:
            for o in options:
                if o.get('final'):
                    dt_start = None
                    dt_end = None

                    # untested using full days instead of timeslots
                    try:
                        dt_start = datetime.datetime.fromtimestamp(o.get('start')/1000 - self.tz_offset)
                    except ValueError:
                        pass
                    try:
                        dt_end = datetime.datetime.fromtimestamp(o.get('end')/1000 - self.tz_offset)
                    except ValueError:
                        pass
                    if dt_start or dt_end:
                        return [(dt_start, dt_end)]

    def is_open(self) -> bool:
        if self.json_file['state'] == 'OPEN':
            return True
        else:
            return False