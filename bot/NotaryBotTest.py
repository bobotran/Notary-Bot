import unittest
import unittest.mock
import NotaryBot
import Managers
import main
import datetime
import pdb
import time
from NotaryBot import SimpleNotaryBot, AcceptDecision, DeclineDecision
from contextlib import contextmanager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import staleness_of


sample_page = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/testpage1.html'
accept_page = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/accept_page.html'
faxback_page = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/faxback.html'
already_filled = 'https://6zkmrwrswzaeisdvykf0fw-on.drv.tw/NotaryBotWebTest/already_filled.html'

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
        wm = Managers.WebManager(sample_page)
        expected = {'When' : datetime.datetime(2019, 6, 21, 19, 30), 'Where' : 'Dove Canyon, CA 92679', 'Fee' : 100}
        self.assertEqual(wm.get_details_dict(), expected)

    def testMonthExtraction(self):
        input = 'Fri Jun 21 at 7:30 pm'
        expected = datetime.datetime(2019, 6, 21, 19, 30)
        wm = Managers.WebManager(sample_page)
        self.assertEqual(wm._str_to_datetime(input), expected)

    def testReadCalendar(self):
        cm = Managers.CalendarManager(-7)
        target_day = datetime.datetime(2019, 7, 23)
        events = cm.get_events_for_day(target_day)
        #self.assertListEqual([event['summary'] for event in events], ['test1', 'test2', 'test3'])
        self.assertListEqual([event['summary'] for event in events], [
                             'Hsueh Signing in Rancho Santa Margarita, CA', 'Wareham Signing in San Clemente, CA', 'Holton Signing in Aliso Viejo, CA'])
    def testAreConflict(self):
        testev1 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 2)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 3)}}

        testev2 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 1, 30)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 2, 30)}}
        testev3 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 2)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 3)}}
        testev4 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 3)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 4)}}
        testev5 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 2, 30)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 2, 45)}}
        testev6 = {'start': {'dateTime' : datetime.datetime(2019, 6, 21, 1)}, 'end':{'dateTime': datetime.datetime(2019, 6, 21, 4)}}
        cm = Managers.CalendarManager(-7)
        self.assertEqual(cm._are_conflicted(testev1, testev2), True)
        self.assertEqual(cm._are_conflicted(testev1, testev3), True)
        self.assertEqual(cm._are_conflicted(testev1, testev4), False)
        self.assertEqual(cm._are_conflicted(testev1, testev5), True)
        self.assertEqual(cm._are_conflicted(testev1, testev6), True)

    def testIsConflict(self):
        cm = Managers.CalendarManager(-7)
        testev1 = {'start': {'dateTime': datetime.datetime(2019, 7, 23, 0, 30, tzinfo=cm.timezone)}, 'end': {'dateTime': datetime.datetime(2019, 7, 23, 1, 30, tzinfo=cm.timezone)}}
        self.assertEqual(cm.is_conflicted(testev1), True)

    # def testDistance(self):
    #     address1 = '11426 Freer Street, Arcadia'
    #     address2 = '37 Sunny Slope, Rancho Santa Margarita'
    #     mm = Managers.MapManager('googlemaps')
    #     self.assertEqual(56, round(mm.get_miles(address1, address2)))

    # def testDistanceIntegration(self):
    #     wm = Managers.WebManager(sample_page)
    #     address1 = wm.get_details_dict()['Where']
    #     address2 = '37 Sunny Slope, Rancho Santa Margarita'
    #     mm = Managers.MapManager('googlemaps')
    #     self.assertEqual(round(6.9), round(mm.get_miles(address2, address1)))

    def testPageLoad(self):
        with unittest.mock.patch.dict('os.environ', {'maxDist': '30', 'minFee': '75', 'home': '37 Sunny Slope, Rancho Santa Margarita', 'timezone': '-7', 'signingDuration': '1', 'mapKey': 'AIzaSyBSdwHPQ05vsAz4a0r49yzLLso7AeBG_-Y', 'environment': 'dev'}):
            wm = Managers.WebManager(already_filled)
            self.assertEqual('this signing order has been filled' in wm.driver.page_source, True)

    def testButtonClick(self):
        wm = Managers.WebManager(faxback_page)
        wm.click_accept_button()
        with wm.wait_for_page_load():
            self.assertEqual('Accept Page', wm.driver.title)

    def testWebsiteIntegrated(self):
        with unittest.mock.patch.dict('os.environ', {'maxDist': '30', 'minFee': '75', 'home': '37 Sunny Slope, Rancho Santa Margarita', 'timezone': '-7', 'signingDuration': '1', 'mapKey': 'AIzaSyBSdwHPQ05vsAz4a0r49yzLLso7AeBG_-Y', 'environment':'dev'}):
            nb = SimpleNotaryBot(sample_page)
            decision = nb.get_prediction()
        self.assertEqual(AcceptDecision.text, decision.text)
        decision.execute()
        with nb.web_manager.wait_for_page_load():
            self.assertEqual('Accept Page', nb.web_manager.driver.title)

if __name__ == "__main__":
    unittest.main()
