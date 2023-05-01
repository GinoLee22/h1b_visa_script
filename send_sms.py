from twilio.rest import Client
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

ACCOUNT_ID = config['TWILIO_SETUP']['ACCOUNT_SID']
AUTH_TOKEN = config['TWILIO_SETUP']['AUTH_TOKEN']
FROM_PHONE_NUMBER = config['TWILIO_SETUP']['FROM_PHONE_NUMBER']
MSG_BODY = config['TWILIO_SETUP']['MSG_BODY']
TO_PHONE_NUMBER = config['TWILIO_SETUP']['TO_PHONE_NUMBER']


def send() -> None:
    client = Client(ACCOUNT_ID, AUTH_TOKEN)
    message = client.messages.create(
        from_=FROM_PHONE_NUMBER,
        body=MSG_BODY,
        to=TO_PHONE_NUMBER,
    )
    print(message)
