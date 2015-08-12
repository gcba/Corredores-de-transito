import hashlib
import urllib
import hmac
import base64
import urlparse
import datetime
import requests
import json
import sys
import api
import time
from waypoints import waypoints_config
api.log_requests = True


class Segment:
    base_url = "https://maps.googleapis.com/maps/api/directions/json"
    client_id = "id"
    client_secret = "secret"

    def __init__(self, origin, destination, waypoints):
        args = {
            "alternatives": False,
            "departure_time": "now",
            "mode": "driving",
            "origin": origin,
            "destination": destination,
            "waypoints": '|'.join(["via:%s" % wp for wp in waypoints])
        }
        input_url = self.base_url + "?" + urllib.urlencode(args)
        self.url = self._sign_url(input_url)
        self.response = None

    def _sign_url(self, input_url):
        input_url += "&client=%s" % self.client_id
        url = urlparse.urlparse(input_url)
        url_to_sign = url.path + "?" + url.query
        decoded_key = base64.urlsafe_b64decode(self.client_secret)
        signature = hmac.new(decoded_key, url_to_sign, hashlib.sha1)
        encoded_signature = base64.urlsafe_b64encode(signature.digest())
        original_url = url.scheme + "://" + url.netloc + url.path + "?" + url.query
        return original_url + "&signature=" + encoded_signature

    def get_directions(self):
        try:
            log('Request %s' % self.url)
            r = requests.get(self.url, timeout=5)
            self.response = json.loads(r.content)
        except Exception as e:
            log(str(e))
            return False
        return True

    def get_time(self):
        travel_time = -1
        try:
            travel_time = self.response['routes'][0]['legs'][0]['duration_in_traffic']['value']
        except Exception as e:
            log(str(e))
        return travel_time


def fetch_data():
    google_maps_data = {}
    for config in waypoints_config:
        log(config['name'] + '. ' + config['description'])
        segment = Segment(config['from'], config['to'], config['waypoints'])
        if segment.get_directions() and segment.get_time() > 0:
            google_maps_data[config['id']] = segment.get_time()
    return google_maps_data


def push_to_api(data_dict, date_now):
    date_string = date_now.strftime('%Y-%m-%dT%H:%M:%S-03:00')
    params = {}
    block = 1
    for key in data_dict:
        params["id%d" % block] = key
        params["data%d" % block] = data_dict[key]
        params["date%d" % block] = date_string
        params["datatype%d" % block] = 'tiempo_viaje'
        block += 1
    log("pushing %s" % str(params))
    try:
        api.Data.dynamic_create(params)
    except Exception as e:
        log(str(e))
    return


def time_to_sleep():
    now = datetime.datetime.now()
    weekday = now.weekday()
    # 0 = monday, 6 = sunday
    hour = now.hour
    minute = now.minute
    if 23 <= hour or hour < 7:
        sleeping_time = 60 - minute
    elif 7 <= hour < 10:
        if weekday < 5:
            sleeping_time = 5 - (minute % 5)
        else:
            sleeping_time = 20 - (minute % 20)
    elif 10 <= hour < 17:
        if weekday < 5:
            sleeping_time = 10 - (minute % 10)
        else:
            sleeping_time = 20 - (minute % 20)
    elif 17 <= hour < 20:
        if weekday < 5:
            sleeping_time = 5 - (minute % 5)
        elif weekday == 6:
            sleeping_time = 10 - (minute % 10)
        else:
            sleeping_time = 20 - (minute % 20)
    else:
        if weekday < 6:
            sleeping_time = 10 - (minute % 10)
        else:
            sleeping_time = 20 - (minute % 20)
    return sleeping_time * 60 - now.second


def sleep():
    sleeping_time = time_to_sleep()
    log('Durmiendo %02d:%02d' % (sleeping_time / 60, sleeping_time % 60))
    time.sleep(sleeping_time)
    return


def log(msj):
    time_string = datetime.datetime.now().isoformat()
    log_msj = time_string + '  ' + msj
    sys.stdout.write("%s\n" % log_msj)
    with open("google_maps.log", "a") as log_file:
        log_file.write("%s\n" % log_msj)

if __name__ == '__main__':
    while True:
        sleep()
        now_date = datetime.datetime.now()
        data = fetch_data()
        push_to_api(data, now_date)
