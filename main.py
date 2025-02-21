import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta

import schedule
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from mailersend import emails
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load configuration from config.json
with open('config.json', 'r') as f:
    config = json.load(f)

LISTING_URL = config['listing_url']
CHECK_INTERVAL = config['check_interval']
EMAIL_SETTINGS = config['email']
DATABASE = 'bookings.db'

# Setup logging
logging.basicConfig(filename='airbnb_monitor.log', level=logging.INFO, format='%(asctime)s %(message)s')


# Initialize database
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (date TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()


# Send email notification using MailerSend
def send_email(subject, body):
    mailer = emails.NewEmail(EMAIL_SETTINGS['api_key'])

    mail_body = {}

    mail_from = {
        "name": EMAIL_SETTINGS['sender_name'],
        "email": EMAIL_SETTINGS['sender'],
    }

    recipients = [
        {
            "name": EMAIL_SETTINGS['recipient_name'],
            "email": EMAIL_SETTINGS['recipient'],
        }
    ]

    reply_to = {
        "name": EMAIL_SETTINGS['reply_name'],
        "email": EMAIL_SETTINGS['reply'],
    }

    mailer.set_mail_from(mail_from, mail_body)
    mailer.set_mail_to(recipients, mail_body)
    mailer.set_subject(subject, mail_body)
    mailer.set_html_content(body, mail_body)
    mailer.set_plaintext_content(body, mail_body)
    mailer.set_reply_to(reply_to, mail_body)

    try:
        mailer.send(mail_body)
        logging.info('Email sent successfully')
    except Exception as e:
        logging.error(f'Failed to send email: {e}')


# Extract availability data from the Airbnb calendar
def extract_availability(driver):
    availability_data = []
    try:
        # Wait for the calendar to load (adjust timeout as needed)
        wait = WebDriverWait(driver, 100)
        logging.info('Hello')
        calendar_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[class="c1e8f4ze atm_9s_1txwivl atm_ks_15vqwwr atm_gz_2bgklt atm_h0_2bgklt atm_e2_1bnz1s5 atm_ks_ewfl5b__oggzyc atm_gz_idpfg4__oggzyc atm_h0_idpfg4__oggzyc dir dir-ltr"]'))  # Use a specific and reliable selector
        )

        # Find all the day elements in the calendar
        day_elements = calendar_element.find_elements(By.CSS_SELECTOR, 'td[role="button"]')  # Specific selector for days

        logging.info(f'Found {len(day_elements)} day elements')

        for day_element in day_elements:
            try:
                # Extract the date from the data-testid attribute of the *inner* div.
                inner_div = day_element.find_element(By.CSS_SELECTOR, 'div[data-testid^="calendar-day-"]')
                date_str = inner_div.get_attribute("data-testid").replace("calendar-day-", "")  # Example: "calendar-day-02/20/2025"
                date_obj = datetime.strptime(date_str, "%m/%d/%Y").date()  # Corrected date format

                # Determine Availability based on data-is-day-blocked attribute
                is_blocked = inner_div.get_attribute("data-is-day-blocked") == 'true'  # Correctly checking a boolean attribute
                logging.info(f"Date: {date_obj}, Blocked: {is_blocked}")

                if datetime.now().date() < date_obj <= datetime.now().date() + timedelta(days=180):
                    availability_data.append({"date": str(date_obj), "booked": is_blocked})

            except Exception as e:
                print(f"Error processing day: {day_element.text}. Error: {e}")  # print day's text for debugging
                continue  # move to the next date

    except Exception as e:
        print(f"Error extracting availability data: {e}")
        return []

    return availability_data


# Check availability of the listing for the next 180 days using Selenium
def check_availability():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    ua = UserAgent()
    options.add_argument(f"user-agent={ua.random}")

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    try:
        driver.get(LISTING_URL)
        availability_data = extract_availability(driver)
        logging.info(f'Availability data: {availability_data}')
        booked_dates = [entry['date'] for entry in availability_data if entry['booked']]
        new_booked_dates = []

        for date in booked_dates:
            if not is_date_in_db(date):
                new_booked_dates.append(date)
                add_date_to_db(date)

        if new_booked_dates:
            send_email('Airbnb Booking Alerte', f'Votre appartement {LISTING_URL} a été réservée pour les dates suivantes :: {", ".join(new_booked_dates)}')
            logging.info(f'The listing {LISTING_URL} has been booked for the following dates: {", ".join(new_booked_dates)}')
        else:
            logging.info('No new bookings found for the next 180 days.')

    except Exception as e:
        logging.error(f'Error checking availability: {e}')
    finally:
        driver.quit()


# Check if a date exists in the database
def is_date_in_db(date):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM bookings WHERE date = ?", (date,))
    exists = c.fetchone() is not None
    conn.close()
    return exists


# Add a date to the database
def add_date_to_db(date):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT INTO bookings (date) VALUES (?)", (date,))
    conn.commit()
    conn.close()


# Schedule the job
def schedule_job():
    schedule.every(CHECK_INTERVAL).minutes.do(check_availability)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    print('Starting the script...')
    init_db()
    check_availability()
    schedule_job()
    print('Script execution completed.')
