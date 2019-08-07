import unittest
import unittest.mock
import NotaryBot
import Managers
#import main
import datetime
import pdb
import time
from NotaryBot import SimpleNotaryBot, AcceptDecision, DeclineDecision
from contextlib import contextmanager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import staleness_of
import os


sample_page = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/testpage1.html'
accept_page = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/accept_page.html'
faxback_page = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/faxback.html'
already_filled = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/already_filled.html'
environment_vars = {
'maxDist': '30', 
'minFee': '75', 
'home': '37 Sunny Slope, Rancho Santa Margarita', 
'timezone': '-7', 
'signingDuration': '1', 
'mapKey': 'AIzaSyBSdwHPQ05vsAz4a0r49yzLLso7AeBG_-Y', 
'environment': 'dev', 
'maxSignings':'5', 
'asapDuration':'2',
'operatingStart' : '8',
'operatingEnd' : '20',
'freenessThres' : '2'
}

class NotaryBotTest(unittest.TestCase):

    def testUrlExtraction(self):
        expected = 'http://snpd.in/KF7XdQ'
        input = """First Class Signing Se...: Signing available on Wed 07/03 at T.B.D., in
        92620 (Irvine).

        http://snpd.in/KF7XdQ to view details and reply.
        YOUR ACCOUNT <https://voice.google.com> HELP CENTER
        <https://support.google.com/voice#topic=1707989> HELP FORUM
        <https://productforums.google.com/forum/#!forum/voice>
        This email was sent to you because you indicated that you'd like to receive
        email notifications for text messages. If you don't want to receive such
        emails in the future, please update your email notification settings
        <https://voice.google.com/settings#messaging>.
        Google LLC
        1600 Amphitheatre Pkwy
        Mountain View CA 94043 USA"""

        self.assertEqual(main.get_snpd_url(input), expected)

    def testGetDetailsDict(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            wm = Managers.WebManager(sample_page)
            expected = {'When' : datetime.datetime(2019, 6, 21, 19, 30), 'Where' : 'Dove Canyon, CA 92679', 'Fee' : 100, 'Qualifier' : None}
            self.assertEqual(wm.get_details_dict(), expected)

    def testMonthExtraction(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            input = 'Fri Jun 21 at 7:30 pm'
            expected = datetime.datetime(2019, 6, 21, 19, 30)
            wm = Managers.WebManager(sample_page)
            self.assertEqual(wm._str_to_datetime(input), expected)

    def testReadCalendar(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            cm = Managers.CalendarManager(Managers.ConfigManager.get_parameters()['Timezone'])
            target_day = datetime.datetime(2019, 7, 23)
            events = cm.get_events_for_day(target_day)
        #self.assertListEqual([event['summary'] for event in events], ['test1', 'test2', 'test3'])
        self.assertListEqual([event['summary'] for event in events], ['Kevin orientation', 'REMOVED Rouse Jr Signing in Trabuco Canyon, CA'])
    def testAreConflict(self):
        testev1 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 2)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 3)}}

        testev2 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 1, 30)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 2, 30)}}
        testev3 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 2)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 3)}}
        testev4 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 3)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 4)}}
        testev5 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 2, 30)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 2, 45)}}
        testev6 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 1)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 4)}}
        with unittest.mock.patch.dict('os.environ', environment_vars):
            cm = Managers.CalendarManager(Managers.ConfigManager.get_parameters()['Timezone'])
        self.assertEqual(cm._are_conflicted(testev1, testev2), True)
        self.assertEqual(cm._are_conflicted(testev1, testev3), True)
        self.assertEqual(cm._are_conflicted(testev1, testev4), False)
        self.assertEqual(cm._are_conflicted(testev1, testev5), True)
        self.assertEqual(cm._are_conflicted(testev1, testev6), True)

    def testIsConflict(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            cm = Managers.CalendarManager(
                Managers.ConfigManager.get_parameters()['Timezone'])
            testev1 = {'start': {'dateTime': datetime.datetime(2019, 7, 23, 0, 30, tzinfo=cm.timezone)}, 'end': {'dateTime': datetime.datetime(2019, 7, 23, 1, 30, tzinfo=cm.timezone)}}
            self.assertEqual(cm.is_conflicted(testev1), True)

    def testDistance(self):
        address1 = '11426 Freer Street, Arcadia'
        address2 = '37 Sunny Slope, Rancho Santa Margarita'
        with unittest.mock.patch.dict('os.environ', environment_vars):
            mm = Managers.MapManager('googlemaps')
            self.assertEqual(56, round(mm.get_miles(address1, address2)))

    def testDistanceIntegration(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            wm = Managers.WebManager(sample_page)
            address1 = wm.get_details_dict()['Where']
            address2 = '37 Sunny Slope, Rancho Santa Margarita'
            mm = Managers.MapManager('googlemaps')
            self.assertEqual(6, round(mm.get_miles(address2, address1)))

    def testPageLoad(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            wm = Managers.WebManager(already_filled)
        self.assertEqual('this signing order has been filled' in wm.driver.page_source, True)

    def testButtonClick(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            wm = Managers.WebManager(faxback_page)
            wm.click_accept_button()
        with wm.wait_for_page_load():
            self.assertEqual('Accept Page', wm.driver.title)

    def testWebsiteIntegrated(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            nb = SimpleNotaryBot(sample_page)
            decision = nb.get_prediction()
            self.assertEqual(DeclineDecision.text, decision.text)
            decision.execute()

    def testPersonalPrefix(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            cm = Managers.CalendarManager(Managers.ConfigManager.get_parameters()['Timezone'])
            target = datetime.datetime(2019, 8, 1)
            self.assertEqual(len(cm.get_signings_for_day(target)), 3)

    def testIsFree(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            cm = Managers.CalendarManager(Managers.ConfigManager.get_parameters()['Timezone'])
            target = datetime.datetime(2019, 8, 1, 8, 30).replace(tzinfo=cm.timezone)
            self.assertEqual(cm.is_free(target, 2), False)

    def testGetEventsBetween(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            cm = Managers.CalendarManager(Managers.ConfigManager.get_parameters()['Timezone'])
            start_datetime = datetime.datetime(2019, 8, 6, 10, tzinfo=cm.timezone)
            end_datetime = datetime.datetime(2019, 8, 6, 16, 15, tzinfo=cm.timezone)
            events = cm.get_events_between(start_datetime, end_datetime)
            self.assertListEqual([ev['summary'] for ev in events], [
                                 'Bravman Signing in Irvine, CA', 'Francis Signing in San Clemente, CA', 'Ta Signing in Lake Forest, CA'])
    
    def testGetUnionEvents(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            dt = datetime.datetime
            cm = Managers.CalendarManager(Managers.ConfigManager.get_parameters()['Timezone'])
            target = datetime.datetime(2019, 8, 6, 10, tzinfo=cm.timezone)
            union_events = cm._get_union_events_for_day(target)
            self.assertListEqual([ev['summary'] for ev in union_events], [
                                 'Bravman Signing in Irvine, CA', 'Francis Signing in San Clemente, CA', 'Ta Signing in Lake Forest, CA', 'Kearney Signing in Irvine, CA'])
            self.assertListEqual([(ev['start']['dateTime'], ev['end']['dateTime']) for ev in union_events], [
                                 (dt(2019, 8, 6, 9, 30, tzinfo=cm.timezone), dt(2019, 8, 6, 10, 30, tzinfo=cm.timezone)), 
                                 (dt(2019, 8, 6, 14, tzinfo=cm.timezone), dt(2019, 8, 6, 15, tzinfo=cm.timezone)), 
                                 (dt(2019, 8, 6, 15, 30, tzinfo=cm.timezone), dt(2019, 8, 6, 16, 30, tzinfo=cm.timezone)),
                                 (dt(2019, 8, 6, 19, 45, tzinfo=cm.timezone), dt(2019, 8, 6, 20, 45, tzinfo=cm.timezone)) ])

    def testHasFree(self):
        with unittest.mock.patch.dict('os.environ', environment_vars):
            dt = datetime.datetime
            param = Managers.ConfigManager.get_parameters()
            cm = Managers.CalendarManager(param['Timezone'])
            free_slots = cm.has_free(dt(2019, 8, 6, 8, tzinfo=cm.timezone), dt(2019, 8, 6, 23, tzinfo=cm.timezone), param['Signing Duration'])
            self.assertEqual(free_slots, 7)

if __name__ == "__main__":
    unittest.main()
