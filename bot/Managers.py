from __future__ import print_function
import selenium
import constants
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.chrome.options import Options
import boto3
from trie import Trie
import re
import pdb
import time
import copy
import math

import datetime
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import googlemaps
import os
from oauth2client.service_account import ServiceAccountCredentials
import logging
import shutil
from contextlib import contextmanager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import staleness_of

logger = logging.getLogger()
logger.setLevel(logging.INFO)
ssm = boto3.client('ssm')


"""
Todo:
    TBD on same day.
    "Outside operating range" for TBD call 8/12
"""
BIN_DIR = "/tmp/bin"
CURR_BIN_DIR = os.getcwd() + "/bin"

def _init_bin(executable_name):
    if not os.path.exists(BIN_DIR):
        logger.info("Creating bin folder")
        os.makedirs(BIN_DIR)
    logger.info("Copying binaries for " + executable_name + " in /tmp/bin")
    currfile = os.path.join(CURR_BIN_DIR, executable_name)
    newfile = os.path.join(BIN_DIR, executable_name)
    if not os.path.exists(newfile):
        shutil.copy2(currfile, newfile)
    logger.info("Giving new binaries permissions for lambda")
    os.chmod(newfile, 0o775)
    logger.info(executable_name + " ready.")

class WebManager:
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    months_trie = Trie(months)
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    days_trie = Trie(days)

    def __init__(self, url_string=None, webdriver=None):
        if webdriver:
            self.driver = webdriver
        else:
            self.driver = WebManager._get_webdriver()
        if url_string:
            self._navigate_to_webpage(url_string)
        self.old_page = None
    # def __del__(self):
    #     self.driver.close()

    def _get_webdriver():
        return WebManager._get_chrome_webdriver()
    def _get_chrome_webdriver():
        chrome_options = Options()

        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--headless")

        if os.environ['environment'] == 'dev':
            driver = webdriver.Chrome(options=chrome_options, executable_path=os.path.join(CURR_BIN_DIR, 'chromedriver.exe'))
        else:
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--window-size=1280x1696')
            chrome_options.add_argument('--user-data-dir=/tmp/user-data')
            chrome_options.add_argument('--hide-scrollbars')
            chrome_options.add_argument('--enable-logging')
            chrome_options.add_argument('--log-level=0')
            chrome_options.add_argument('--v=99')
            chrome_options.add_argument('--single-process')
            chrome_options.add_argument('--data-path=/tmp/data-path')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--homedir=/tmp')
            chrome_options.add_argument('--disk-cache-dir=/tmp/cache-dir')
            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36')

            chrome_options.binary_location = os.path.join(CURR_BIN_DIR, "headless-chromium")
            driver = webdriver.Chrome(chrome_options=chrome_options, executable_path=os.path.join(CURR_BIN_DIR, 'chromedriver'))

        logger.info('WebDriver {} created successfully'.format(driver))
        return driver

    def _get_firefox_webdriver(self):
        options = webdriver.FirefoxOptions()
        options.headless = True
        options.add_argument("-headless")
        #options.set_headless(headless = True)
        cap = DesiredCapabilities().FIREFOX
        cap["marionette"] = False
        binary = FirefoxBinary('C:\\Users\\Ryan Tran\\AppData\\Local\\Apps\\Mozilla Firefox\\firefox.exe')
        return webdriver.Firefox(options = options, firefox_binary = binary, capabilities=cap, executable_path='C:\\Users\\Ryan Tran\\Downloads\\geckodriver-v0.24.0-win64\\geckodriver.exe')

    def _get_index_of(self, search_str, str_list, guess):
        """
        Returns index in str_list that contains search_str.
        Returns None if no element in str_list contains search_str.
        """
        for offset in range(len(str_list)):
            position = (guess + offset) % len(str_list)
            if search_str.lower() in str_list[position].lower():
                return position
        return None

    def _str_to_datetime(self, dt_str, timezone=None):
        """
        Parses strings in the format 'Fri Jun 21 at 7:30 pm'
        """
        dt_list = dt_str.split()
        month_index = 1
        try:
            matching_months = WebManager.months_trie.start_with_prefix(dt_list[month_index])
        except IndexError:
            logger.info('When field was of length 1. Unable to convert to datetime. Returning None.')
            return None
        assert len(matching_months) == 1, 'There is not exactly one match for ' + dt_list[month_index]
        
        month = matching_months[0].val
        day = int(dt_list[month_index + 1])
        year = datetime.datetime.now(timezone).year
        if datetime.datetime.now(timezone).month == 12 and month == 1:
            year += 1
            
        time_index = self._get_index_of(':', dt_list, 4)
        if time_index:
            time_substr = dt_list[time_index]
            assert ':' in time_substr, 'No time defined for signing.'

            hr = int(time_substr.split(':')[0])
            mn = int(time_substr.split(':')[1])
            if dt_list[time_index + 1].lower() == 'pm':
                hr = hr % 12 + 12
            else:
                assert dt_list[time_index + 1].lower() == 'am', 'Sixth element of detail list is neither AM nor PM'
            when = datetime.datetime(year, month, day, hour=hr, minute=mn, tzinfo=timezone)
            logger.info('Processed {} into datetime {}'.format(dt_str, when))
            return when
        else:
            when = datetime.datetime(year, month, day, tzinfo=timezone)
            logger.info('Processed {} into datetime {}'.format(dt_str, when))
            return when
    def _is_prescheduled(self, dt_str):
        dt_list = dt_str.split()
        return self._get_index_of(':', dt_list, 4) is not None and self._get_index_of(CalendarManager.BEFORE, dt_list, 3) is None and self._get_index_of(CalendarManager.AFTER, dt_list, 3) is None
    def _get_qualifier(self, dt_str):
        dt_list = dt_str.split()
        guess = -1
        for offset in range(len(dt_list)):
            position = (guess + offset) % len(dt_list)
            elem = dt_list[position].replace('.','').lower()
            if elem in [CalendarManager.ASAP, CalendarManager.TBD, CalendarManager.MORNING, CalendarManager.AFTERNOON, CalendarManager.EVENING, CalendarManager.BEFORE, CalendarManager.AFTER]:
                return elem
        return None
    def _get_provider(self):
        provider_class_name = 'automator-details__message-label'
        contents = self.driver.find_elements_by_class_name(provider_class_name)
        content = [elem.text for elem in contents if elem.text.startswith('About ')]
        return content[0].replace('About ', '')
    def _navigate_to_webpage(self, url_string):
        '''
        Navigates to the webpage specified by url_string.
        '''
        self.driver.get(url_string)
        logger.info('Navigated to {}'.format(url_string))

    def set_url(self, url_string):
        self.old_page = self.driver.find_element_by_tag_name('html')
        self._navigate_to_webpage(url_string)

    @contextmanager
    def wait_for_page_load(self, timeout=10):
        yield WebDriverWait(self.driver, timeout).until(staleness_of(self.old_page))

    def get_details_dict(self, timezone=None):
        details_class_name = 'dl-horizontal'
        content = self.driver.find_element_by_class_name(details_class_name)
        details = [elem.text for elem in content.find_elements_by_css_selector('*')]
        qualifier = self._get_qualifier(details[details.index('When') + 1])
        when = self._str_to_datetime(details[details.index('When') + 1], timezone=timezone)
        where = details[details.index('Where') + 1].replace(' map', '')
        fee_line = details[details.index('Your fee') + 1]
        dollar_amount = None
        for word in fee_line.split():
            if '$' in word:
                dollar_amount = word.replace('$', '')
        fee = int(dollar_amount)
        return {'When' : when, 'Where' : where, 'Fee' : fee, 'Qualifier' : qualifier, 'Provider' : self._get_provider()}

    def click_accept_button(self):
        try:
            accept = self.driver.find_element_by_partial_link_text('available')
            logger.info('Trying simple accept action...')
        except selenium.common.exceptions.NoSuchElementException:
            logger.info('Carousel accept page detected. Attempting "Interested" and "Available" click.')
            content = self.driver.find_element_by_class_name('automator-offer__options')
            button = content.find_element_by_tag_name('button')
            button.click()

            carousel = self.driver.find_element_by_class_name('carousel-inner')
            accept = carousel.find_element_by_partial_link_text('available')
        self.old_page = self.driver.find_element_by_tag_name('html')
        accept.click()
        logger.info('Accept link {} clicked.'.format(accept))

class CalendarManager:
    TBD = 'tbd'
    ASAP = 'asap'
    EVENING = 'evening'
    MORNING = 'morning'
    AFTERNOON = 'afternoon'
    BEFORE = 'before'
    AFTER = 'after'
    PERSONAL_PREFIX = 'P:'
    REMOVED = 'REMOVED'

    def __init__(self, timezone, start_time=None, quitting_time=None):
        self.timezone = timezone
        self.events = None
        self.union_events = None
        self.operating_start = start_time
        self.operating_end = quitting_time
        if not self.operating_start:
            self.operating_start = datetime.time(hour=8, tzinfo=self.timezone)
        if not self.operating_end:
            self.operating_end = datetime.time(hour=20, tzinfo=self.timezone)

    def _get_creds(self):
        SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']

        creds = None
        if os.environ['environment'] == 'dev':
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
        else:
            creds = self._load_token_s3(constants.TOKEN_KEY)
            logger.info('Fetched credentials {} from s3'.format(creds))

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info('Credentials refreshed.')
            else:
                logger.info('ono the user needs to login. Undefined behavior coming up.')
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            if os.environ['environment'] == 'dev':
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            else:
                self._save_token_s3(constants.TOKEN_KEY, pickle.dumps(creds))
                logger.info('Token {} saved to s3'.format(creds))
        return creds

    def _save_token_s3(self, key, token_bytes):
        s3 = boto3.client('s3')
        s3.put_object(Body=token_bytes, Bucket=constants.SES_BUCKET, Key=key)
    def _load_token_s3(self, key):
        s3 = boto3.client('s3')
        o = s3.get_object(Bucket=constants.SES_BUCKET, Key=key)
        return pickle.loads(o['Body'].read())

    def _are_conflicted(self, ev1, ev2):
        if ev1['start']['dateTime'] <= ev2['start']['dateTime'] and ev2['start']['dateTime'] < ev1['end']['dateTime']:
            return True
        elif ev2['start']['dateTime'] >= ev1['end']['dateTime']:
            return False
        else:
            if ev2['end']['dateTime'] <= ev1['start']['dateTime']:
                return False
            else:
                return True
            
    def _get_union_events_for_day(self, target, skip_cache=False):
        if self.union_events is None or skip_cache:
            logger.info('Creating union events...')
            events = copy.deepcopy(self.get_events_for_day(target))
            index = 0
            while index < len(events) - 1:
                curr_event, next_event = events[index], events[index + 1]
                if curr_event['start']['dateTime'] <= next_event['start']['dateTime'] and next_event['start']['dateTime'] < curr_event['end']['dateTime']:
                    curr_event['end']['dateTime'] = max(curr_event['end']['dateTime'], next_event['end']['dateTime'])
                    events.pop(index + 1)
                else:
                    index += 1
            self.union_events = events
        else:
            logger.info('Using cached union events.')
        return self.union_events
    
    def _convert_datetime_events(self, events):
        for ev in events:
            try:
                ev['start']['dateTime'] = datetime.datetime.fromisoformat(ev['start']['dateTime'])
                ev['end']['dateTime'] = datetime.datetime.fromisoformat(ev['end']['dateTime'])
            except TypeError:
                pass

    def is_conflicted(self, new_event):
        """
        Returns: Whether ev1 conflicts with the other events on the calendar for that day
        """
        assert isinstance(new_event['start']['dateTime'], datetime.datetime) and isinstance(new_event['end']['dateTime'], datetime.datetime), 'Start and end times are not datetimes.'
        events = self.get_events_for_day(new_event['start']['dateTime'])
        for ev in events:
            if self._are_conflicted(new_event, ev):
                return True
        return False

    def is_free(self, start_datetime, duration):
        signing_ev = {'start': {'dateTime': start_datetime},
                      'end': {'dateTime': start_datetime + datetime.timedelta(hours=duration)}}
        if signing_ev['start']['dateTime'].time().replace(tzinfo=self.timezone) < self.operating_start or signing_ev['end']['dateTime'].time().replace(tzinfo=self.timezone) > self.operating_end:
            logger.info('Signing is outside of operating time.')
            return False
        return not self.is_conflicted(signing_ev)

    def has_free(self, start_datetime, end_datetime, duration):
        """
        Args:
            duration: length in hours
        Returns # of free time slots of length duration in between start_datetime and end_datetime
        Assumes start_datetime and end_datetime are on the same day.
        """
        def _get_free_slots_between(s_datetime, e_datetime):
            free_slots = (e_datetime - s_datetime) / datetime.timedelta(hours=duration)
            if free_slots < 0:
                return 0
            else:
                return math.trunc(free_slots)

        if start_datetime.timetz() < self.operating_start:
            start_datetime = datetime.datetime.combine(start_datetime.date(), self.operating_start)
        if end_datetime.timetz() > self.operating_end:
            end_datetime = datetime.datetime.combine(end_datetime.date(), self.operating_end)
        
        events = self.get_events_between(start_datetime, end_datetime, events=self._get_union_events_for_day(start_datetime))
        if len(events) == 0:
            return _get_free_slots_between(start_datetime, end_datetime)
        total_free_slots = 0
        total_free_slots += _get_free_slots_between(start_datetime, events[0]['start']['dateTime'])
        for index in range(len(events) - 1):
            curr_event, next_event = events[index], events[index + 1]
            total_free_slots += _get_free_slots_between(curr_event['end']['dateTime'], next_event['start']['dateTime'])
        total_free_slots += _get_free_slots_between(events[-1]['end']['dateTime'], end_datetime)
        return total_free_slots

    
    def get_events_between(self, start_datetime, end_datetime, events=None):
        """
        Returns list of events between start_datetime and end_datetime.
        Assumes start_datetime and end_datetime are on the same day.
        """
        if events is None:
            events = self.get_events_for_day(start_datetime)

        events_after_start = []
        for ev in events:
            if start_datetime >= ev['end']['dateTime']:
                continue
            events_after_start.append(ev)
        result = []
        for ev in events_after_start:
            if end_datetime <= ev['start']['dateTime']:
                continue
            result.append(ev)
        return result

    def get_events_for_day(self, target, skip_cache=False):
        """
        Args:
            target: datetime.datetime that represents the date for the requested events.
        """
        if self.events is None or skip_cache:
            assert isinstance(target, datetime.datetime), 'Target event is not a datetime.'
            creds = self._get_creds()
            logger.info('Credentials {} loaded.'.format(creds))
            service = build('calendar', 'v3', credentials=creds,
                            cache_discovery=False)

            # Call the Calendar API
            day_start = datetime.datetime(target.year, target.month, target.day, tzinfo=self.timezone).isoformat()
            day_end = datetime.datetime(target.year, target.month, target.day, hour=23, minute=59, second=59, tzinfo=self.timezone).isoformat()
            events_result = service.events().list(calendarId='primary', timeMin=day_start,
                                                timeMax=day_end, singleEvents=True,
                                                orderBy='startTime').execute()
            logger.info('Events results {} received'.format(events_result))
            self.events = events_result.get('items', [])
            self._convert_datetime_events(self.events)
        else:
            logger.info('Using cached events from previous Calendar API call.')
        return self.events

    def get_signings_for_day(self, target):
        events = self.get_events_for_day(target)
        return [ev for ev in events if not ev['summary'].startswith(CalendarManager.PERSONAL_PREFIX) and not ev['summary'].startswith(CalendarManager.REMOVED)]

class MapManager:
    def __init__(self, client_str):
        if client_str == 'googlemaps':
            api_key = os.environ['mapKey']
            self.client = self._get_googlemaps_client(api_key)

    def _get_googlemaps_client(self, API_key):
        return googlemaps.Client(key=API_key)

    def get_miles(self, origin, dest):
        meters = self.client.distance_matrix(origin, dest, mode='driving', units='metric', avoid='tolls')["rows"][0]["elements"][0]["distance"]["value"]
        logger.info('Miles from {} to {} = {}'.format(
            origin, dest, round(meters * 0.000621371, ndigits=1)))
        logger.info('Distance Matrix queried.')
        return round(meters * 0.000621371, ndigits=1)
    def get_seconds(self, origin, dest):
        return self.client.distance_matrix(origin, dest, mode='driving', units='imperial', avoid='tolls')["rows"][0]["elements"][0]["duration"]["value"]

class ConfigManager:
    SSM_PREFIX = '/notarybot/prod/'
    def get_parameters():
        if os.environ['configLocation'] == 'ssm':
            logger.info('Fetching parameters from SSM...')
            tz = datetime.timezone(datetime.timedelta(hours=int(ConfigManager.get_ssm_parameter('timezone'))))
            return {'Max Dist': int(ConfigManager.get_ssm_parameter('maxDist')), 
            'Min Fee': int(ConfigManager.get_ssm_parameter('minFee')), 
            'Home': os.environ['home'], 
            'Timezone': tz, 
            'Signing Duration': int(ConfigManager.get_ssm_parameter('signingDuration')), 
            'ASAP Duration': int(ConfigManager.get_ssm_parameter('asapDuration')), 
            'Max Signings': int(ConfigManager.get_ssm_parameter('maxSignings')),
            'Operating Start': datetime.time(hour=int(ConfigManager.get_ssm_parameter('operatingStart')), tzinfo=tz),
            'Operating End' : datetime.time(hour=int(ConfigManager.get_ssm_parameter('operatingEnd')), tzinfo=tz),
            'Freeness Threshold' : int(ConfigManager.get_ssm_parameter('freenessThres')),
            'Provider Preferences' : eval(ConfigManager.get_ssm_parameter('providerPreferences')) }
        else:
            logger.info('Fetching parameters from environment variables...')
            tz = datetime.timezone(datetime.timedelta(hours=int(os.environ['timezone'])))
            return {'Max Dist': int(os.environ['maxDist']), 
            'Min Fee': int(os.environ['minFee']), 
            'Home': os.environ['home'], 
            'Timezone': tz, 
            'Signing Duration': int(os.environ['signingDuration']), 
            'ASAP Duration': int(os.environ['asapDuration']), 
            'Max Signings': int(os.environ['maxSignings']),
            'Operating Start': datetime.time(hour=int(os.environ['operatingStart']), tzinfo=tz),
            'Operating End' : datetime.time(hour=int(os.environ['operatingEnd']), tzinfo=tz),
            'Freeness Threshold' : int(os.environ['freenessThres']),
            'Provider Preferences' : eval(os.environ['providerPreferences']) }

    def get_ssm_parameter(param):
        full_path = ConfigManager.SSM_PREFIX + param
        response = ssm.get_parameter(Name=full_path, WithDecryption=True)
        return response['Parameter']['Value']

