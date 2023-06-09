# -*- coding: utf8 -*-

import time
import json
import random
import platform
import configparser
from datetime import datetime

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from send_sms import send

config = configparser.ConfigParser()
config.read('config.ini')

USERNAME = config['USVISA']['USERNAME']
PASSWORD = config['USVISA']['PASSWORD']
SCHEDULE_ID = config['USVISA']['SCHEDULE_ID']
MY_SCHEDULE_DATE = config['USVISA']['MY_SCHEDULE_DATE']
COUNTRY_CODE = config['USVISA']['COUNTRY_CODE']
FACILITY_ID = config['USVISA']['FACILITY_ID']

SENDGRID_API_KEY = config['SENDGRID']['SENDGRID_API_KEY']
PUSH_TOKEN = config['PUSHOVER']['PUSH_TOKEN']
PUSH_USER = config['PUSHOVER']['PUSH_USER']

LOCAL_USE = config['CHROMEDRIVER'].getboolean('LOCAL_USE')
HUB_ADDRESS = config['CHROMEDRIVER']['HUB_ADDRESS']

REGEX_CONTINUE = "//a[contains(text(),'Continue')]"
XPATH_SCHEDULE_APPOINTMENT = "//title"

DATE_FORMAT = "%Y-%m-%d"
DATE_LOWER_BOUND = datetime.strptime(
    config['DESIRED_DATE']['LOWER_BOUND'], DATE_FORMAT).date()
DATE_UPPER_BOUND = datetime.strptime(
    config['DESIRED_DATE']['UPPER_BOUND'], DATE_FORMAT).date()


# def MY_CONDITION(month, day): return int(month) == 11 and int(day) >= 5
# No custom condition wanted for the new scheduled date
def MY_CONDITION(month, day): return True


SECONDS_TO_RUN = int(config['RETRY']['SECONDS_TO_RUN'])
RETRY_INTERVAL = int(config['RETRY']['RETRY_INTERVAL'])

STEP_TIME = 0.5  # time between steps (interactions with forms): 0.5 seconds
EXCEPTION_TIME = 60*30  # wait time when an exception occurs: 30 minutes
# wait time when temporary banned (empty list): 60 minutes
COOLDOWN_TIME = 60*60

DATE_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/schedule/{SCHEDULE_ID}/appointment/days/{FACILITY_ID}.json?appointments[expedite]=false"
TIME_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/schedule/{SCHEDULE_ID}/appointment/times/{FACILITY_ID}.json?date=%s&appointments[expedite]=false"
APPOINTMENT_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/schedule/{SCHEDULE_ID}/appointment"
APPOINTMENT_REFERAL_URL = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv/schedule/{SCHEDULE_ID}/continue_actions"
APPOINTMENT_INFO_URI = f"https://ais.usvisa-info.com/{COUNTRY_CODE}/niv"

EXIT = False


def send_notification(msg):
    print(f"Sending notification: {msg}")

    if SENDGRID_API_KEY:
        message = Mail(
            from_email=USERNAME,
            to_emails=USERNAME,
            subject=msg,
            html_content=msg)
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.message)

    if PUSH_TOKEN:
        url = "https://api.pushover.net/1/messages.json"
        data = {
            "token": PUSH_TOKEN,
            "user": PUSH_USER,
            "message": msg
        }
        requests.post(url, data)


def get_driver():
    if LOCAL_USE:
        dr = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    else:
        dr = webdriver.Remote(command_executor=HUB_ADDRESS,
                              options=webdriver.ChromeOptions())
    return dr


driver = get_driver()


def login():
    # Bypass reCAPTCHA
    driver.get(APPOINTMENT_INFO_URI)
    time.sleep(STEP_TIME)
    a = driver.find_element(By.XPATH, '//a[@class="down-arrow bounce"]')
    a.click()
    time.sleep(STEP_TIME)

    print("Login start...")
    href = driver.find_element(
        By.XPATH, '//*[@id="header"]/nav/div[1]/div[1]/div[2]/div[1]/ul/li[3]/a')

    href.click()
    time.sleep(STEP_TIME)
    Wait(driver, 60).until(EC.presence_of_element_located((By.NAME, "commit")))

    print("\tclick bounce")
    a = driver.find_element(By.XPATH, '//a[@class="down-arrow bounce"]')
    a.click()
    time.sleep(STEP_TIME)

    do_login_action()


def do_login_action():
    print("\tinput email")
    user = driver.find_element(By.ID, 'user_email')
    user.send_keys(USERNAME)
    time.sleep(random.randint(1, 3))

    print("\tinput pwd")
    pw = driver.find_element(By.ID, 'user_password')
    pw.send_keys(PASSWORD)
    time.sleep(random.randint(1, 3))

    print("\tclick privacy")
    box = driver.find_element(By.CLASS_NAME, 'icheckbox')
    box .click()
    time.sleep(random.randint(1, 3))

    print("\tcommit")
    btn = driver.find_element(By.NAME, 'commit')
    btn.click()
    time.sleep(random.randint(1, 3))

    Wait(driver, 60).until(
        EC.presence_of_element_located((By.XPATH, XPATH_SCHEDULE_APPOINTMENT)))
    print("\tlogin successful!")


def get_date():
    if not is_logged_in():
        login()
        return get_date()
    else:
        driver.get(APPOINTMENT_URL)
        # to get json data from server need to set the http header with json
        request = driver.execute_script(
            "var req = new XMLHttpRequest();" +
            "req.open('GET', '" + str(DATE_URL) + "', false);" +
            "req.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');" +
            "req.setRequestHeader('X-Requested-With', 'XMLHttpRequest');" +
            "req.send(null);return req.responseText;"
        )
    date = json.loads(request)
    return date


def get_time(date: str):
    time_url = TIME_URL % date
    request = driver.execute_script(
        "var req = new XMLHttpRequest();" +
        "req.open('GET', '" + str(time_url) + "', false);" +
        "req.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');" +
        "req.setRequestHeader('X-Requested-With', 'XMLHttpRequest');" +
        "xhr.setRequestHeader('Referer', ", + APPOINTMENT_REFERAL_URL + ");" +
        "req.send(null);" +
        "return req.responseText;"
    )
    time = json.loads(request)["available_times"]
    print(f"Got time successfully! {date} {time}")
    return time


def reschedule(date: str):
    global EXIT
    print(f"Starting Reschedule ({date})")

    time = get_time(date)
    driver.get(APPOINTMENT_URL)
    data = {
        "utf8": driver.find_element(by=By.NAME, value='utf8').get_attribute('value'),
        "authenticity_token": driver.find_element(by=By.NAME, value='authenticity_token').get_attribute('value'),
        "confirmed_limit_message": driver.find_element(by=By.NAME, value='confirmed_limit_message').get_attribute('value'),
        "use_consulate_appointment_capacity": driver.find_element(by=By.NAME, value='use_consulate_appointment_capacity').get_attribute('value'),
        "appointments[consulate_appointment][facility_id]": FACILITY_ID,
        "appointments[consulate_appointment][date]": date,
        "appointments[consulate_appointment][time]": time,
    }

    headers = {
        "User-Agent": driver.execute_script("return navigator.userAgent;"),
        "Referer": APPOINTMENT_URL,
        "Cookie": "_yatri_session=" + driver.get_cookie("_yatri_session")["value"]
    }

    r = requests.post(APPOINTMENT_URL, headers=headers, data=data)
    if (r.text.find('successfully') != -1):
        msg = f"Rescheduled successfully! {date} {time}"
        send_notification(msg)
        EXIT = True
    else:
        msg = f"Reschedule Failed. {date} {time}"
        send_notification(msg)


def is_logged_in():
    # try to hit appointment link to verify the login status.
    # "Attend Appointment" -> Logged in. Otherwise no.
    driver.get(APPOINTMENT_INFO_URI)
    content = driver.page_source
    if (content.find("Attend Appointment") == -1):
        return False
    return True


def print_dates(dates):
    print("Available dates:")
    for d in dates:
        print("%s \t business_day: %s" %
              (d.get('date'), d.get('business_day')))
    print()


last_seen = None


def get_available_date(dates):
    global last_seen

    def is_earlier(date):
        my_date = datetime.strptime(MY_SCHEDULE_DATE, "%Y-%m-%d")
        new_date = datetime.strptime(date, "%Y-%m-%d")
        result = my_date > new_date
        print(f'Is {my_date} > {new_date}:\t{result}')
        return result

    print("Checking for an earlier date:")
    for d in dates:
        date = d.get('date')
        if is_earlier(date) and date != last_seen:
            _, month, day = date.split('-')
            if (MY_CONDITION(month, day)):
                last_seen = date
                return date


def push_notification(dates):
    msg = "date: "
    for d in dates:
        msg = msg + d.get('date') + '; '
    send_notification(msg)


def get_desired_date_found(dates):
    date = datetime.strptime(dates[0]['date'], DATE_FORMAT).date()
    if date >= DATE_LOWER_BOUND and date <= DATE_UPPER_BOUND:
        return date
    return None


if __name__ == "__main__":
    login()
    retry_limit = SECONDS_TO_RUN // RETRY_INTERVAL
    retry_count = 0
    while 1:
        if retry_count > retry_limit:
            break
        try:
            print("------------------")
            print(datetime.today())
            print(f"Retry count: {retry_count}")
            print()

            dates = get_date()
            if not dates:
                retry_count += 1
                raise Exception("No dates found")
            else:
                desired_date = get_desired_date_found(dates)
                if desired_date:
                    reschedule(desired_date)
                else:
                    retry_count += 1
                    print("No desired date found")
                    time.sleep(RETRY_INTERVAL)
                    # Twillo need to verify the free number. It is manual.
                    # send()
            # if not dates:
            #     msg = "List is empty"
            #     send_notification(msg)
            #     EXIT = True
            # print_dates(dates)
            # date = get_available_date(dates)
            # print()
            # print(f"New date: {date}")
            # if date:
            #     reschedule(date)
            #     push_notification(dates)

            if (EXIT):
                print("------------------exit")
                break

            # if not dates:
            #     msg = "List is empty"
            #     send_notification(msg)
            #     # EXIT = True
            #     time.sleep(COOLDOWN_TIME)
            # else:
            #     time.sleep(RETRY_TIME)

        except Exception as ex:
            # print the error message to debugging
            print(f"Exception: {ex}")
            retry_count += 1
            time.sleep(EXCEPTION_TIME)

    if (not EXIT):
        send_notification("HELP! Crashed.")
