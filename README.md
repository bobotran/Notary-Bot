# NotaryBot
## AWS Lambda application to automate event scheduling. 
Upon AWS SES incoming email trigger, this application scrapes the webpage contained in the email for salient details 
then calls the Google Calendar and Google Distance Matrix APIs before deciding whether or not to sign the user up for this event.
