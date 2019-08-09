import Managers
from abc import ABC, abstractmethod
import datetime
import os
import time

class NotaryBot(ABC):
    """
    Abstract Base Class
    """
    def __init__(self, url_string, webdriver=None):
        super().__init__()
        param = Managers.ConfigManager.get_parameters() 
        self.web_manager = Managers.WebManager(url_string, webdriver=webdriver)
        self.calendar_manager = Managers.CalendarManager(param['Timezone'], start_time=param['Operating Start'], quitting_time=param['Operating End'])
        self.map_manager = Managers.MapManager('googlemaps')

    @abstractmethod
    def get_prediction(self, snpd_url):
        pass

class SimpleNotaryBot(NotaryBot):
    def __init__(self, url_string, webdriver=None):
        super().__init__(url_string, webdriver=webdriver)

    def get_prediction(self):
        details = self.web_manager.get_details_dict()
        Managers.logger.info('Details {} retrieved.'.format(details))
        param = Managers.ConfigManager.get_parameters()
        Managers.logger.info('Parameters {} retrieved.'.format(param))
        if details['Fee'] < param['Min Fee']:
            Managers.logger.info('Fee too low. Declining.')
            return DeclineDecision(self.web_manager)

        Managers.logger.info('Checking number of signings...')
        if len(self.calendar_manager.get_signings_for_day(details['When'].replace(tzinfo=self.calendar_manager.timezone))) > param['Max Signings']:
            Managers.logger.info('Too many signings for the day. Declining.')
            return DeclineDecision(self.web_manager)
        
        if not details['Qualifier']:
            Managers.logger.info('Checking if predetermined timeslot is free...')
            start_datetime = details['When'].replace(tzinfo=self.calendar_manager.timezone)
            if not self.calendar_manager.is_free(start_datetime, param['Signing Duration']):
                Managers.logger.info('Time conflict. Declining.')
                return DeclineDecision(self.web_manager)
        
        Managers.logger.info('Checking distance...')
        if self.map_manager.get_miles(param['Home'], details['Where']) > param['Max Dist']:
            Managers.logger.info('Signing is too far. Declining.')
            return DeclineDecision(self.web_manager)
        if details['Qualifier'] == Managers.CalendarManager.BEFORE:
            day_beginning = datetime.datetime.combine(details['When'].date(), self.calendar_manager.operating_start)
            free_slots = self.calendar_manager.has_free(day_beginning, details['When'], param['Signing Duration'])
            Managers.logger.info('Detected {} free slots for {}'.format(free_slots, Managers.CalendarManager.BEFORE))
            if free_slots < param['Freeness Threshold']:
                return DeclineDecision(self.web_manager)
        if details['Qualifier'] == Managers.CalendarManager.AFTER:
            day_end = datetime.datetime.combine(details['When'].date(), self.calendar_manager.operating_end)
            free_slots = self.calendar_manager.has_free(details['When'], day_end, param['Signing Duration'])
            Managers.logger.info('Detected {} free slots for {}'.format(free_slots, Managers.CalendarManager.AFTER))
            if free_slots < param['Freeness Threshold']:
                return DeclineDecision(self.web_manager)
        elif details['Qualifier'] == Managers.CalendarManager.ASAP:
            Managers.logger.info('Processing ASAP appointment.')
            start_datetime = datetime.datetime.now(self.calendar_manager.timezone)
            if not self.calendar_manager.is_free(start_datetime, param['ASAP Duration']):
                Managers.logger.info('Upcoming events too close for ASAP appointment. Declining.')
                return DeclineDecision(self.web_manager)
        elif details['Qualifier'] == Managers.CalendarManager.MORNING:
            start_datetime = datetime.datetime.combine(details['When'].date(), self.calendar_manager.operating_start)
            end_datetime = datetime.datetime.combine(details['When'].date(), datetime.time(hour=12))
            free_slots = self.calendar_manager.has_free(start_datetime, end_datetime, param['Signing Duration'])
            Managers.logger.info('Detected {} free slots for the {}'.format(free_slots, Managers.CalendarManager.MORNING))
            if free_slots < param['Freeness Threshold']:
                return DeclineDecision(self.web_manager)
        elif details['Qualifier'] == Managers.CalendarManager.AFTERNOON:
            start_datetime = datetime.datetime.combine(details['When'].date(), datetime.time(hour=12))
            end_datetime = datetime.datetime.combine(details['When'].date(), datetime.time(hour=17))
            free_slots = self.calendar_manager.has_free(start_datetime, end_datetime, param['Signing Duration'])
            Managers.logger.info('Detected {} free slots for the {}'.format(free_slots, Managers.CalendarManager.AFTERNOON))
            if free_slots < param['Freeness Threshold']:
                return DeclineDecision(self.web_manager)
        elif details['Qualifier'] == Managers.CalendarManager.EVENING:
            start_datetime = datetime.datetime.combine(details['When'].date(), datetime.time(hour=17))
            end_datetime = datetime.datetime.combine(details['When'].date(), self.calendar_manager.operating_end)
            free_slots = self.calendar_manager.has_free(start_datetime, end_datetime, param['Signing Duration'])
            Managers.logger.info('Detected {} free slots for the {}'.format(free_slots, Managers.CalendarManager.EVENING))
            if free_slots < param['Freeness Threshold']:
                return DeclineDecision(self.web_manager)
        elif details['Qualifier'] == Managers.CalendarManager.TBD:
            start_datetime = datetime.datetime.combine(details['When'].date(), self.calendar_manager.operating_start)
            end_datetime = datetime.datetime.combine(details['When'].date(), self.calendar_manager.operating_end)
            free_slots = self.calendar_manager.has_free(start_datetime, end_datetime, param['Signing Duration'])
            Managers.logger.info('Detected {} free slots for the {}'.format(free_slots, Managers.CalendarManager.TBD))
            if free_slots < param['Freeness Threshold']:
                return DeclineDecision(self.web_manager)
        return AcceptDecision(self.web_manager)
        

class Decision(ABC):
    def __init__(self, web_manager):
        self.web_manager = web_manager
    @abstractmethod
    def execute(self):
        pass

class AcceptDecision(Decision):
    text = 'accept'
    def __init__(self, web_manager):
        super().__init__(web_manager)
    def execute(self):
        self.web_manager.click_accept_button()
        Managers.logger.info('Signing accepted.')
        with self.web_manager.wait_for_page_load(timeout=10):
            Managers.logger.info('Stayed on same page: {}'.format('Are you available for this signing' in self.web_manager.driver.page_source))
            Managers.logger.info('Already taken: {}'.format('signing order has been filled' in self.web_manager.driver.page_source))

class DeclineDecision(Decision):
    text = 'decline'
    def __init__(self, web_manager):
        super().__init__(web_manager)
    def execute(self):
        Managers.logger.info('Signing declined.')
