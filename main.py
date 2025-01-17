#!/usr/bin/env python
# coding: utf-8

import argparse
import ast
import glob
import json
import os
import random
import sys
import time
from datetime import datetime
from sys import stdout
from nameparser import HumanName

import vobject
import vobject.vcard
from dotenv import load_dotenv
from lxml import html
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from sqlite_utils import Database
from vobject.base import ValidateError
from webdriver_manager.chrome import ChromeDriverManager

import utils

os.system('cls' if os.name == 'nt' else 'clear')

# Set up environment
if os.path.exists('.env'):
    fb_user = os.getenv('fb_user')
    fb_pass = os.getenv('fb_pass')
else:
    print(
        "Welcome! Let's set up your environment. This will create a .env file in the same folder as this script, "
        "and set it up with your email, password, and Mapbox API Key. This is saved only on your device and only used "
        "to autofill the Facebook login form.\n")

    fb_user = input("Facebook Email Address: ")
    fb_pass = input("Facebook Password: ")

    f = open(".env", "w+")
    f.write('fb_user="' + fb_user + '"\n')
    f.write('fb_pass="' + fb_pass + '"\n')
    f.close()

    print("\nGreat! Details saved in .env, so you shouldn't need to do this again.\n")

# Prepare database
friends_html = 'db/friend_list.html'
profiles_dir = 'db/profiles/'

db_index = 'friend_list'
db_profiles = 'profiles'

if not os.path.exists(profiles_dir):
    os.makedirs(profiles_dir)


# Configure browser
def start_browser():
    # Setup browser
    print("Opening Browser...")
    options = Options()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--mute-audio")
    options.add_argument("--start-maximized")
    # options.add_argument("headless")
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))


# Login
def sign_in():
    fb_start_page = 'https://m.facebook.com/'
    load_dotenv()
    if os.getenv('fb_pass', None):
        fb_user = os.getenv('fb_user')
        fb_pass = os.getenv('fb_pass')
        print("Logging in %s automatically..." % fb_user)
        browser.get(fb_start_page)
        try:
            WebDriverWait(browser, 10).until(expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[value='Only allow essential cookies']"))).click()
        except TimeoutException:
            pass  # No cookies screen
        email_id = browser.find_element(By.ID, "m_login_email")
        pass_id = browser.find_element(By.ID, "m_login_password")
        email_id.send_keys(fb_user)
        pass_id.send_keys(fb_pass)
        WebDriverWait(browser, 10).until(expected_conditions.element_to_be_clickable((By.NAME, 'login'))).click()
        WebDriverWait(browser, 10).until(expected_conditions.element_to_be_clickable(
            (By.XPATH, '//*[@id="root"]/div[1]/div/div/div[3]/div[1]/div/div/a'))).click()
    else:
        browser.get(fb_start_page)
        input("Please log into facebook and press enter after the page loads...")


# Download friends list
def download_friends_page():
    browser.get("https://m.facebook.com/me/friends")
    print('Opening friends page on Facebook...')
    time.sleep(3)

    page_number = 1
    while browser.find_elements(By.CSS_SELECTOR, '#m_more_friends'):
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        stdout.write("\r>> Scrolled to page %d" % page_number)
        stdout.flush()
        page_number += 1
        time.sleep(0.5)

    with open(friends_html, 'w', encoding="utf-8") as f:
        f.write(browser.page_source)
        print("\n>> Saved friend page to '%s'" % friends_html)


# Add friends from HTML page to database
def create_friends_index():
    print('Reading Facebook friends page file...')
    file_path = os.getcwd() + '/' + friends_html
    x = html.parse(file_path, html.HTMLParser(encoding='utf-8')).xpath
    base = '(//*[@data-sigil="undoable-action"])'
    num_items = len(x(base))
    if num_items == 0:
        print("\nWasn't able to parse friends index. This probably means that Facebook updated their template.\n"
              "Please raise an issue on Github and I will try to update the script.\n"
              "Or if you can code, please submit a pull request instead :)\n")
        sys.exit()

    existing_index = utils.db_read(db_index)
    existing_ids = []
    for i, d in enumerate(existing_index):
        existing_ids.append(d['id'])

    for i in range(1, num_items + 1):
        b = base + '[' + str(i) + ']/'
        info = json.loads(x(b + '/div[3]/div/div/div[3]')[0].get('data-store'))
        stdout.flush()
        stdout.write("\rScanning friend ... (%d / %d)" % (i, num_items))

        if info['id'] not in existing_ids:
            name = x(b + '/div[2]//a')[0].text
            alias = '' if info['is_deactivated'] else x(b + '/div[2]//a')[0].get('href')[1:]
            d = {
                'id': info['id'],
                'name': name,
                'active': 0 if int(info['is_deactivated']) else 1,
                'alias': alias
            }

            utils.db_write(db_index, d)

    print('\n>> Added (%s) friends to index %s' % (num_items, db_index))


# Download profile pages
def download_profiles():
    index = utils.db_read(db_index)
    print('Downloading profiles...')
    session_downloads = 0
    for i, d in enumerate(index):
        if d['active']:
            fname = profiles_dir + str(d['id']) + '.html'
            if not os.path.exists(fname):
                print('- %s (# %s)' % (d['name'], d['id']))
                browser.get('https://mbasic.facebook.com/profile.php?v=info&id=' + str(d['id']))
                session_downloads += 1
                time.sleep(random.randint(1, 3))
                if session_downloads == 45:
                    print("Taking a voluntary break at " + str(
                        session_downloads) + " profile downloads to prevent triggering Facebook's alert systems."
                                             "I recommend you quit (Ctrl-C or quit this window) to play it safe and "
                                             "try coming back tomorrow to space it out.")
                    input("Or, press enter to continue at your own risk.")
                if browser.title == "You Can't Use This Feature Right Now":
                    print(
                        "\n***WARNING***\n\n"
                        "Facebook detected abnormal activity, so this script is going play it safe and take a break.\n"
                        "As of March 2020, this seems to happen after downloading ~45 profiles in 1 session.\n"
                        "I recommend not running the script again until tomorrow.\n"
                        "Excessive use might cause Facebook to get more suspicious and possibly suspend your "
                        "account.\n\n "
                        "If you have experience writing scrapers, please feel free to recommend ways to avoid "
                        "triggering Facebook's detection system :)")
                    sys.exit(1)
                if browser.find_elements(By.CSS_SELECTOR, '#login_form') or browser.find_elements(By.CSS_SELECTOR,
                                                                                                  '#mobile_login_bar'):
                    print('\nBrowser is not logged into facebook! Please run again to login & resume.')
                    sys.exit(1)
                else:
                    with open(fname, 'w', encoding="utf-8") as f:
                        f.write(browser.page_source)


# Parse profile pages into JSON
def parse_profile(profile_file):
    xp_queries = {
        'tagline': {'do': 1, 'txt': '//*[@id="root"]/div[1]/div[1]/div[2]/div[2]'},
        'about': {'do': 1, 'txt': '//div[@id="bio"]/div/div/div'},
        'quotes': {'do': 1, 'txt': '//*[@id="quote"]/div/div/div'},
        'rel': {'do': 1, 'txt': '//div[@id="relationship"]/div/div/div'},
        'rel_partner': {'do': 1, 'href': '//div[@id="relationship"]/div/div/div//a'},
        'details': {'do': 1, 'table': '(//div[not(@id)]/div/div/table[@cellspacing]/tbody/tr//'},
        'work': {'do': 1, 'workedu': '//*[@id="work"]/div[1]/div/div'},
        'education': {'do': 1, 'workedu': '//*[@id="education"]/div[1]/div/div'},
        'family': {'do': 1, 'fam': '//*[@id="family"]/div/div/div'},
        'life_events': {'do': 1, 'years': '(//div[@id="year-overviews"]/div/div/div/div/div)'}
    }

    profile_id = int(os.path.basename(profile_file).split('.')[0])
    profile_path = 'file://' + os.getcwd() + '/' + profile_file
    x = html.parse(profile_path, html.HTMLParser(encoding='utf-8')).xpath
    alias = x('//a/text()[. = "Timeline"][1]/..')[0].get('href')[1:].split('?')[0]
    d = {
        'id': profile_id,
        'name': x('//head/title')[0].text,
        'alias': alias if alias != 'profile.php' else '',
        'meta_created': time.strftime('%Y-%m-%d', time.localtime(os.path.getctime(profile_file))),
        'details': []
    }
    stdout.flush()
    stdout.write("\r>> Parsing: %s (# %s)                    " % (d['name'], d['id']))

    for k, v in xp_queries.items():
        if v['do'] == 1:
            if 'txt' in v:
                elements = x(v['txt'])
                if len(elements) > 0:
                    d[str(k)] = str(x(v['txt'])[0].text_content())
            elif 'href' in v:
                elements = x(v['href'])
                if len(elements) > 0:
                    d[str(k)] = x(v['href'])[0].get('href')[1:].split('refid')[0][:-1]
            elif 'table' in v:
                rows = x(v['table'] + 'td[1])')
                for i in range(1, len(rows) + 1):
                    key = x(v['table'] + 'td[1])' + '[' + str(i) + ']')[0].text_content()
                    val = x(v['table'] + 'td[2])' + '[' + str(i) + ']')[0].text_content()
                    d['details'].append({key: val})
            elif 'workedu' in v:
                d[str(k)] = []
                base = v['workedu']
                rows = x(base)
                for i in range(1, len(rows) + 1):
                    # Prep the Work/Education object
                    dd = {}
                    workedu_base = base + '[' + str(i) + ']' + '/div/div[1]/div[1]'
                    dd['org'] = x(workedu_base)[0].text_content()

                    # Determine org URL
                    if str(k) == "work":
                        org_href = workedu_base + '/span/a'  # work URL
                    else:
                        org_href = workedu_base + '/div/span/a'  # edu URL

                    # Include org URL if exists
                    url_elements = x(org_href)
                    if len(url_elements) > 0:
                        dd['link'] = x(org_href)[0].get('href')[1:].split('refid')[0][:-1]

                    dd['lines'] = []
                    lines = x(base + '[' + str(i) + ']' + '/div/div[1]/div')
                    for l in range(2, len(lines) + 1):
                        line = x(base + '[' + str(i) + ']' + '/div/div[1]/div' + '[' + str(l) + ']')[0].text_content()
                        dd['lines'].append(line)

                    d[str(k)].append(dd)

            elif 'fam' in v:
                d[str(k)] = []
                base = v['fam']
                rows = x(base)
                for i in range(1, len(rows) + 1):
                    xp_alias = x(base + '[' + str(i) + ']' + '//h3[1]/a')
                    alias = '' if len(xp_alias) == 0 else xp_alias[0].get('href')[1:].split('refid')[0][:-1]
                    d[str(k)].append({
                        'name': x(base + '[' + str(i) + ']' + '//h3[1]')[0].text_content(),
                        'rel': x(base + '[' + str(i) + ']' + '//h3[2]')[0].text_content(),
                        'alias': alias
                    })
            elif 'life_events' in k:
                d[str(k)] = []
                base = v['years']
                years = x(base)
                for i in range(1, len(years) + 1):
                    year = x(base + '[' + str(i) + ']' + '/div[1]/text()')[0]
                    events = x(base + '[' + str(i) + ']' + '/div/div/a')
                    for e in range(1, len(events) + 1):
                        event = x('(' + base + '[' + str(i) + ']' + '/div/div/a)' + '[' + str(e) + ']')
                        d[str(k)].append({
                            'year': year,
                            'title': event[0].text_content(),
                            'link': event[0].get('href')[1:].split('refid')[0]
                        })
    return d


# Parse all unparsed profiles in db profile folder
def parse_profile_files():
    print('>> Scanning downloaded profile pages...')
    already_parsed = []
    profiles = utils.db_read(db_profiles)
    for data in profiles:
        already_parsed.append(data['id'])

    profile_files = glob.glob(profiles_dir + '*.html')
    for profile_file in profile_files:
        profile_id = int(os.path.basename(profile_file).split('.')[0])
        if profile_id not in already_parsed:
            data = parse_profile(profile_file)
            if data is not False:
                utils.db_write(db_profiles, data)

    print('>> %s profiles parsed to %s' % (len(profile_files), db_profiles))


def export_to_vcard():
    if not os.path.exists('db/vcards'):
        os.makedirs('db/vcards')

    table = Database('db/data.db')['profiles']
    vcard_file = "db/vcards/{:d}.vcf"

    for table_row in table.rows:
        card = vobject.vCard()
        details = {k: v for d in ast.literal_eval(table_row['details']) for k, v in d.items()}
        work = {k: v for d in ast.literal_eval(table_row['work']) for k, v in d.items()}
        birthday = details.get('Birthday', '')
        if ',' in birthday:
            birthday = datetime.strptime(birthday, "%B %d, %Y").date().isoformat()
        elif birthday is not '':
            birthday = datetime.strptime(birthday, "%B %d").date().isoformat()

        name = HumanName(table_row.get('name', ''))
        card.add('n').value = vobject.vcard.Name(given=name.first, family=name.last, prefix=name.title, suffix=name.suffix)
        card.add('fn').value = name.full_name
        card.add("gender").value = details.get('Gender', '')
        card.add("bday").value = birthday
        card.add("org").value = [work.get('org', '')]

        # TODO add other personalia
        # card.add("adr").value = details.get('Address', '') add parsing for structured addresses https://deepparse.org/
        # card.adr.type_param = 'HOME'
        # card.add("tel").value = details.get('Mobile', '')
        # card.add("lang").value = details.get('Languages', '')
        # card.add("url").value = details.get('Facebook', '')
        try:
            with open(vcard_file.format(table_row.get('id')), 'w+', encoding="utf-8") as f:
                f.write(card.serialize())
        except ValidateError:
            print(f"Issue with generating vCard for {table_row.get('name', '')} with id {table_row.get('id'):d}")


def parse_arguments():
    parser = argparse.ArgumentParser(prog='Facebook Vcard exporter',
                                     description='A program to export profiles of Facebook friends to Vcards')
    parser.add_argument('--list', action='store_true', help='Only download friends page')
    parser.add_argument('--index', action='store_true', help='Only create friends index')
    parser.add_argument('--download', action='store_true', help='Only download friends profiles')
    parser.add_argument('--parse', action='store_true', help='Only parse profiles to database')
    parser.add_argument('--vcard', action='store_true', help='Only export database to vCard files')
    parser.add_argument('--json', action='store_true', help='Only export database to JSON files')
    return parser.parse_args()


# Shell application
if __name__ == '__main__':
    args = parse_arguments()

    try:
        if args.list or args.download or not any(vars(args).values()):
            browser = start_browser()
            sign_in()

        # Download friends list
        if args.list:
            download_friends_page()

        # Index friends list
        if args.index:
            create_friends_index()

        # Download profiles
        if args.download:
            download_profiles()

        # Parse profiles
        if args.parse:
            parse_profile_files()

        # vCard Export
        if args.vcard:
            export_to_vcard()

        # JSON Export (Optional)
        if args.json:
            utils.db_to_json()

        if not any(vars(args).values()):
            download_friends_page()
            create_friends_index()
            download_profiles()
            parse_profile_files()
            export_to_vcard()

        try:
            browser.close()
        except NameError:
            # No browser open
            pass

    except KeyboardInterrupt:
        print('\nThanks for using the script! Please raise any issues on Github.')
        pass
