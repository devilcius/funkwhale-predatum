import json
import ssl
import time
from http.client import HTTPSConnection
import urllib.request
import urllib.error
import urllib.parse
from urllib.error import URLError, HTTPError
from http.client import BadStatusLine
from .funkwhale_startup import PLUGIN
import hashlib

LOGIN_SCROBBLER_URL = "https://api.predatum.com/api/login"
HOST_NAME = "api.predatum.com"
PATH_SUBMIT = "/api/scrobble"
SSL_CONTEXT = ssl.create_default_context()


class Track:

    def __init__(self, artist_name, track_title, release_name=None, additional_info={}):
        self.artist_name = artist_name
        self.track_title = track_title
        self.release_name = release_name
        self.additional_info = additional_info

    @staticmethod
    def from_dict(data):
        return Track(
            data["artist_name"],
            data["track_title"],
            data.get("release_name", None),
            data.get("additional_info", {}),
        )

    def to_dict(self):
        return {
            "artist_name": self.artist_name,
            "track_title": self.track_title,
            "release_name": self.release_name,
            "additional_info": self.additional_info,
        }

    def __repr__(self):
        return "Track(%s, %s)" % (self.artist_name, self.track_title)


class PredatumScrobbler:

    def __init__(self, username, password):
        self.__next_request_time = 0
        self.logger = PLUGIN["logger"]
        hashedAuth = hashlib.md5(
            (username + " " + password).encode("utf-8")
        ).hexdigest()           
        self.token_cache_key = "predatum:sessionkey:{}".format(hashedAuth)
        self.username = username
        self.password = password
        self.setToken()

    def submit(self, listened_at, track):

        payload = _get_payload(track, listened_at)
        return self._submit("single", payload)

    def _submit(self, listen_type, payload, retry=0):
        self._wait_for_ratelimit()
        self.logger.info("ListenPredatum %s: %r", listen_type, payload)
        headers = {
            "Authorization": "Bearer %s" % self.token,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        body = json.dumps(payload)
        conn = HTTPSConnection(HOST_NAME, context=SSL_CONTEXT)
        conn.request("POST", PATH_SUBMIT, body, headers)
        response = conn.getresponse()
        response_text = response.read()
        try:
            response_data = json.loads(response_text)
        except json.decoder.JSONDecodeError:
            response_data = response_text

        self._handle_ratelimit(response)
        log_msg = "Response %s: %r" % (response.status, response_data)
        if response.status == 429 and retry < 5:  # Too Many Requests
            self.logger.warning(log_msg)
            return self._submit(listen_type, payload, retry + 1)
        elif response.status == 401 and retry < 5:
            self.logger.warning(log_msg)
            self.setToken()
            return self._submit(listen_type, payload, retry + 1)
        elif response.status == 201:
            self.logger.debug(log_msg)
        else:
            self.logger.error(log_msg)
        return response

    def _wait_for_ratelimit(self):
        now = time.time()
        if self.__next_request_time > now:
            delay = self.__next_request_time - now
            self.logger.debug("Rate limit applies, delay %d", delay)
            time.sleep(delay)

    def _handle_ratelimit(self, response):
        remaining = int(response.getheader("X-RateLimit-Remaining", 0))
        reset_in = int(response.getheader("X-RateLimit-Reset-In", 0))
        self.logger.debug("X-RateLimit-Remaining: %i", remaining)
        self.logger.debug("X-RateLimit-Reset-In: %i", reset_in)
        if remaining == 0:
            self.__next_request_time = time.time() + reset_in

    def setToken(self, renew = False):
        token = PLUGIN["cache"].get(self.token_cache_key)
        if not token or renew:
            token = self.login()
        
        self.token = token

    def login(self):
        logger = PLUGIN["logger"]        
        params = dict(username = self.username,
                        password = self.password,
                        remember = '1',
                        submit = 'Submit')
        data = urllib.parse.urlencode(params).encode('utf-8')
        try:
            request = urllib.request.Request(LOGIN_SCROBBLER_URL, data)
            response = urllib.request.urlopen(request)
            jsonResponse = json.loads(response.read().decode('utf-8'))
            
            return jsonResponse['token']
        except HTTPError as e:
            logger.info('The server couldn\'t fulfill the authentication request.')
            logger.info('Error code: {}'.format(e.read()))
        except URLError as e:
            print('We failed to reach a server.')
            print(('Reason: ', e.reason))
        except BadStatusLine as e:
            print(("the status line can’t be parsed as a valid HTTP/1.0 or 1.1 status line: ", e.line))  


def _get_payload(track, listened_at=None):
    data = {"track_metadata": track.to_dict()}
    if listened_at is not None:
        data["listened_at"] = listened_at
    return data
