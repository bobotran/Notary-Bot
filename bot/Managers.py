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
logger = logging.getLogger()
logger.setLevel(logging.INFO)


"""
Todo:
    Fix get_details_dict to put None in fields it can't read ('When')
    Have NotaryBot halt when details dict contains any None

    Figure out logger
    Move CalendarManager credentials.json and MapManager API key to environment variables
    (InstalledAppFlow.from_environment_variables?)
    Change WebManager constructor to _navigate_to_webpage automatically
    Run full integration test with sam local invoke
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
        os.rename(currfile, newfile)
    logger.info("Giving new binaries permissions for lambda")
    os.chmod(newfile, 0o775)
    logger.info(executable_name + " ready.")

class WebManager:
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    months_trie = Trie(months)
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    days_trie = Trie(days)

    def __init__(self, url_string=None):
        self.driver = self._get_webdriver()
        if url_string:
            self._navigate_to_webpage(url_string)
    def __del__(self):
        self.driver.close()
    #@classmethod

    def _get_webdriver(self):
        return self._get_chrome_webdriver()
    def _get_chrome_webdriver(self):
        chrome_options = Options()

        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
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

        # _init_bin("headless-chromium")
        # _init_bin("chromedriver")
        # chrome_options.binary_location = os.path.join(BIN_DIR, "headless-chromium")
        # driver = webdriver.Chrome(chrome_options=chrome_options, executable_path=os.path.join(BIN_DIR, 'chromedriver'))

        chrome_options.binary_location = os.path.join(CURR_BIN_DIR, "headless-chromium")
        driver = webdriver.Chrome(chrome_options=chrome_options, executable_path=os.path.join(CURR_BIN_DIR, 'chromedriver'))

        # chrome_options.add_argument("--disable-gpu")
        # chrome_options.add_argument("--headless")
        # driver = webdriver.Chrome(options=chrome_options, executable_path='C:\\Users\\Ryan Tran\\Desktop\\Work\\notarybot\\Notarybot\\bot\\bin\\chromedriver.exe')

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

    def _str_to_datetime(self, dt_str):
        """
        Parses strings in the format 'Fri Jun 21 at 7:30 pm'
        """
        dt_list = dt_str.split()
        matching_months = WebManager.months_trie.start_with_prefix(dt_list[1])
        assert len(matching_months) == 1, 'There is not exactly one match for ' + dt_list[1]

        year = datetime.datetime.now().year
        month = matching_months[0].val
        day = int(dt_list[2])

        time_substr = dt_list[4]
        assert ':' in time_substr, 'No time defined for signing.'

        hr = int(time_substr.split(':')[0])
        mn = int(time_substr.split(':')[1])
        if dt_list[5].lower() == 'pm':
            hr = hr % 12 + 12
        else:
            assert dt_list[5].lower() == 'am', 'Sixth element of detail list is neither AM nor PM'
        logger.info('Processed {} into datetime {}'.format(dt_str, datetime.datetime(year, month, day, hour=hr, minute=mn)))
        return datetime.datetime(year, month, day, hour=hr, minute=mn)


    def _navigate_to_webpage(self, url_string):
        '''
        Navigates to the webpage specified by url_string.
        '''
        self.driver.get(url_string)
    def set_url(self, url_string):
        self._navigate_to_webpage(url_string)
    def get_details_dict(self):
        details_class_name = 'dl-horizontal'
        content = self.driver.find_element_by_class_name(details_class_name)
        details = [elem.text for elem in content.find_elements_by_css_selector('*')]
        when = self._str_to_datetime(details[details.index('When') + 1])
        where = details[details.index('Where') + 1].replace(' map', '')
        fee_line = details[details.index('Your fee') + 1]
        dollar_amount = None
        for word in fee_line.split():
            if '$' in word:
                dollar_amount = word.replace('$', '')
        fee = int(dollar_amount)
        return {'When' : when, 'Where' : where, 'Fee' : fee}

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
        accept.click()
        logger.info('Accept link {} clicked.'.format(accept))

class CalendarManager:
    def __init__(self, timezone_offset):
        self.timezone = datetime.timezone(datetime.timedelta(hours=timezone_offset))
    # def _get_creds(self):
    #     SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']
    #     creds = None
    #     # The file token.pickle stores the user's access and refresh tokens, and is
    #     # created automatically when the authorization flow completes for the first
    #     # time.
    #     if os.path.exists('token.pickle'):
    #         with open('token.pickle', 'rb') as token:
    #             creds = pickle.load(token)

    #     # If there are no (valid) credentials available, let the user log in.
    #     if not creds or not creds.valid:
    #         if creds and creds.expired and creds.refresh_token:
    #             creds.refresh(Request())
    #         else:
    #             flow = InstalledAppFlow.from_client_secrets_file(
    #                 'credentials.json', SCOPES)
    #             creds = flow.run_local_server(port=0)
    #         # Save the credentials for the next run
    #         with open('token.pickle', 'wb') as token:
    #             pickle.dump(creds, token)
    #     return creds

    def _get_creds(self):
        SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']
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
    def is_conflicted(self, new_event):
        """
        Returns: Whether ev1 conflicts with the other events on the calendar for that day
        """
        assert isinstance(new_event['start']['dateTime'], datetime.datetime) and isinstance(new_event['end']['dateTime'], datetime.datetime), 'Start and end times are not datetimes.'
        events = self.get_events_for_day(new_event['start']['dateTime'])
        for ev in events:
            try:
                ev['start']['dateTime'] = datetime.datetime.fromisoformat(ev['start']['dateTime'])
                ev['end']['dateTime'] = datetime.datetime.fromisoformat(ev['end']['dateTime'])
            except TypeError:
                pass
            if self._are_conflicted(new_event, ev):
                return True
        return False

    def get_events_for_day(self, target):
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
        events = events_result.get('items', [])
        return events

class MapManager:
    def __init__(self, client_str):
        if client_str == 'googlemaps':
            #rename calendarKey lol
            api_key = os.environ['mapKey']
            self.client = self._get_googlemaps_client(api_key)
            logger.info('googlemaps client {} created'.format(self.client))

    def _get_googlemaps_client(self, API_key):
        return googlemaps.Client(key=API_key)

    def get_miles(self, origin, dest):
        meters = self.client.distance_matrix(origin, dest, mode='driving', units='metric')["rows"][0]["elements"][0]["distance"]["value"]
        logger.info('Miles from {} to {} = {}'.format(
            origin, dest, round(meters * 0.000621371, ndigits=1)))
        return round(meters * 0.000621371, ndigits=1)
    def get_seconds(self, origin, dest):
        return self.client.distance_matrix(origin, dest, mode='driving', units='imperial')["rows"][0]["elements"][0]["duration"]["value"]