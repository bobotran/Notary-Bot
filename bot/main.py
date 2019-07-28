import email
import json
import os
import boto3
from NotaryBot import SimpleNotaryBot
from Managers import logger
import re
import selenium

SES_INCOMING_BUCKET = 'ses-notarybot'

s3 = boto3.client('s3')


def handler(event, context):
    record = event['Records'][0]
    assert record['eventSource'] == 'aws:s3'
    o = s3.get_object(Bucket=SES_INCOMING_BUCKET,
                      Key=record['s3']['object']['key'])
    raw_mail = o['Body'].read()
    msg = email.message_from_bytes(raw_mail)
    msg_string = msg.get_payload()[0].as_string()
    logger.info('Message string received from s3 {}: {}'.format(record['s3']['object']['key'], msg_string))

    if not is_assignment_notification(msg_string):
        try:
            url_string = get_snpd_url(msg_string)
            nb = SimpleNotaryBot(url_string)
            prediction = nb.get_prediction()
            logger.info('Decision for signing at {}: {}'.format(url_string, prediction.text))
            prediction.execute()
            return prediction.text
        except (AssertionError, selenium.common.exceptions.NoSuchElementException) as e:
            logger.error(e)
    else:
        logger.info('Message recognized as already assigned. Skipped.')



def get_snpd_url(msg_str):
    '''
    Returns None if match cannot be found in msg_str.
    '''
    snpd_regex = 'http[s]?://snpd.in/[^\s]+'
    return re.search(snpd_regex, msg_str).group()

def is_assignment_notification(msg_str):
    '''
    Returns whether the current message indicates an assignment rather than an offer.
    '''
    assignment_regex = "You've been assigned"
    try:
        return bool(re.search(assignment_regex, msg_str).group())
    except AttributeError:
        return False
