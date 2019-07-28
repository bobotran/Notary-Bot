import Managers
from abc import ABC, abstractmethod
import datetime
import os
import time

class NotaryBot(ABC):
    """
    Abstract Base Class
    """
    def __init__(self, url_string):
        super().__init__()
        self.web_manager = Managers.WebManager(url_string)
        Managers.logger.info('Read {} as timezone.'.format(os.environ['timezone']))
        self.calendar_manager = Managers.CalendarManager(int(os.environ['timezone']))
        self.map_manager = Managers.MapManager('googlemaps')

    @abstractmethod
    def get_prediction(self, snpd_url):
        pass

class SimpleNotaryBot(NotaryBot):
    def __init__(self, url_string):
        super().__init__(url_string)

    def _get_parameters(self):
        return {'Max Dist': int(os.environ['maxDist']), 'Min Fee': int(os.environ['minFee']), 'Home': os.environ['home'], 'Timezone':int(os.environ['timezone']), 'Signing Duration':int(os.environ['signingDuration'])}

    def get_prediction(self):
        details = self.web_manager.get_details_dict()
        Managers.logger.info('Details {} retrieved.'.format(details))
        param = self._get_parameters()
        Managers.logger.info('Parameters {} retrieved.'.format(param))
        if details['Fee'] < param['Min Fee']:
            Managers.logger.info('Fee too low. Declining.')
            return DeclineDecision(self.web_manager)
        start_datetime = details['When'].replace(tzinfo=self.calendar_manager.timezone)
        signing_ev = {'start': {'dateTime' : start_datetime}, 
        'end':{'dateTime': start_datetime + datetime.timedelta(hours=param['Signing Duration'])}}
        if self.calendar_manager.is_conflicted(signing_ev):
            Managers.logger.info('Time conflict. Declining.')
            return DeclineDecision(self.web_manager)

        if self.map_manager.get_miles(param['Home'], details['Where']) > param['Max Dist']:
            Managers.logger.info('Signing is too far. Declining.')
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
        with nb.web_manager.wait_for_page_load(timeout=10):
            Managers.logger.info('Stayed on same page: {}'.format('Are you available for this signing' in self.web_manager.driver.page_source))
            Managers.logger.info('Already taken: {}'.format('signing order has been filled' in self.web_manager.driver.page_source))

class DeclineDecision(Decision):
    text = 'decline'
    def __init__(self, web_manager):
        super().__init__(web_manager)
    def execute(self):
        Managers.logger.info('Signing declined.')
