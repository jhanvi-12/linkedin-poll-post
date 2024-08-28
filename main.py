"""This module script is used to create poll in linkedin group"""

import csv
import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
import requests
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Configuration
POLL_FILE = "polls.txt"
COOKIES_FILE = "cookies.json"
CSV_FILE = "output.csv"

# Setup WebDriver
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)


# Read the CSV file and convert it into a list of tuples.
if os.path.isfile(CSV_FILE):
    df_existing = pd.read_csv(CSV_FILE)
else:
    df_existing = pd.DataFrame()  # Create an empty DataFrame
    logger.error("CSV file is empty.")


def check_internet(url="http://www.google.com/", timeout=5):
    """This function is used to check the internet connection.

    Args:
        url (str): check the google url for the connection.
                    Defaults to 'http://www.google.com/'.
        timeout (int, optional): timeout to fetch the url. Defaults to 5.

    Returns:
        boolean: True if internet is connected else False.
    """
    try:
        requests.get(url, timeout=timeout)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


def wait_for_internet():
    """This function is wait for the internet connection if it will disconnected."""
    while not check_internet():
        logger.error("No internet connection. Waiting...")
        time.sleep(5)  # wait for 5 seconds before retrying
    logger.info("Internet connection restored.")


def poll_questions():
    """This function is used to list a poll questions.

    Returns:
        list: Questions list with answers.
    """
    with open(POLL_FILE, "r") as file:
        lines = file.read().strip().split("\n")

    # Parse questions and options
    questions = []
    question = None
    for line in lines:
        line = line.strip()  # Remove leading and trailing whitespace
        if not line:
            continue  # Skip empty lines
        if line[0].isdigit():  # New question
            if question:
                questions.append(question)
            question = {"question": line, "options": []}
        elif question:
            question["options"].append(line)

    # Append the last question
    if question:
        questions.append(question)

    # Create lists for each question with options
    question_lists = [[q["question"]] + q["options"] for q in questions]

    return question_lists


def save_cookies(path: str):
    """This function is used to Save the cookies from the Selenium WebDriver to a file.

    Args:
        driver (webdriver): The Selenium WebDriver instance from which to save cookies.
        path (str): The file path where the cookies will be saved.

    Returns:
        None
    """
    if not os.path.exists(path):
        with open(path, "w") as file:
            json.dump(driver.get_cookies(), file)


def load_cookies(path: str):
    """
    This function is used to load cookies from a file and add them to the Selenium WebDriver.

    Args:
        driver (webdriver): The Selenium WebDriver instance to which cookies will be added.
        path (str): The file path from which to load cookies.

    Returns:
        bool: True if cookies were successfully loaded and added, False otherwise.
    """
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r") as file:
            cookies = json.load(file)
            for cookie in cookies:
                driver.add_cookie(cookie)
        return True
    return False


def login():
    """This function is used to logged in with linkedin acconut."""
    driver.get("https://www.linkedin.com/login")
    input("Enter your code manually ........")
    save_cookies(COOKIES_FILE)


def check_group_url_existing(df, group_url: str):
    """Check if the group URL already exists in the dataframe.

    Args:
        df (pd.DataFrame): Dataframe containing the existing group
        group_url (str): URL of the group.
    Returns:
        bool: True if the group URL already exists, False otherwise.
    """
    if df.empty:
        logger.error("DataFrame is empty.")
        return False
    # Check if required columns are present
    if "Group_URL" not in df.columns:
        logger.error("Required columns are not present in the DataFrame.")
        return False

    # Check if the specific entry already exists
    existing_entry = df[(df["Group_URL"] == group_url)]

    if not existing_entry.empty:
        logger.info("The entry already exists.")
        return True
    else:
        return False


def check_existing_entry(df, group_id: str, poll_text: str):
    """
    Check if the group ID and poll text already exist in the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame containing existing group IDs and polls.
        group_id (str): Group ID to check.
        poll_text (str): Poll text to check.

    Returns:
        bool: True if the entry exists, False otherwise.
    """
    poll_txt = "\n".join(poll_text)
    parts = re.split(r"(\?|\.)", poll_txt)
    question_id = int(parts[0])

    if df.empty:
        logger.error("DataFrame is empty.")
        return False
    # Check if required columns are present
    if "Group_ID" not in df.columns or "Question_ID" not in df.columns:
        logger.error("Required columns are not present in the DataFrame.")
        return False

    # Check if the specific entry already exists
    existing_entry = df[
        (df["Group_ID"] == int(group_id)) & (df["Question_ID"] == question_id)
    ]

    if not existing_entry.empty:
        logger.info("The entry already exists.")
        return True
    else:
        return False


def create_poll(group_url: str):
    """This function is used to create a poll for a group in user's group.

    Args:
        group_url (str): The group url to create a poll for

    Returns:
        poll_text: Question text of the poll.
    """
    driver.get(group_url)
    # Before performing actions, ensure internet is connected
    wait_for_internet()

    time.sleep(10)  # Wait for page to load
    polls = poll_questions()

    num_of_questions = 3
    if len(polls) < num_of_questions:
        num_of_questions = len(polls)

    random_questions = random.sample(polls, num_of_questions)
    created_polls = []
    for poll_text in random_questions:
        # Check if URL already visited before creating new poll.
        if check_group_url_existing(df_existing, group_url):
            logger.info(f"The poll already exists in the group :- {group_url}")
            continue
        try:
            question = poll_text[0].split(".")[1].strip()
            # Note: Validate poll text length as linkedin provides.
            if len(question) > 140:
                logger.error(
                    f"Poll question '{poll_text[0]}' exceeds 140 characters. Skipping..."
                )
                continue

            # Note: Validate options length as linkedin provides.
            options = poll_text[1:]
            if any(len(option) > 30 for option in options):
                logger.info(
                    f"One or more options exceed 30 characters. Skipping poll question '{poll_text[0]}'..."
                )
                continue

            logger.debug("Group URL :", group_url)
            if group_url.split("/")[-1] == "":
                group_id = group_url.split("/")[-2]
            else:
                group_id = group_url.split("/")[-1]

            if check_existing_entry(df_existing, group_id, poll_text):
                poll_ques = poll_text[0].split(".")[1].strip()
                logger.info(
                    f"Skipping already processed group {group_url} with poll: {poll_ques}"
                )
                continue

            wait_for_internet()
            poll_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[.//span[text()='Poll']]")
                )
            )
            if not poll_button:
                logger.error(f"No poll button found in group {group_url}. Skipping...")
                pass
            else:
                logger.debug("**** In Poll creation button click ****")
                poll_button.click()

                # Enter poll details
                label = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "artdeco-text-input--label")
                    )
                )
                input_id = label.get_attribute("for")

                # Use the input ID to locate the corresponding textarea element
                poll_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, input_id))
                )

                poll_input.send_keys(question)

                # Add options (for example, 2 options)
                options = poll_text[1:]
                for i, option in enumerate(options[:4]):
                    option_input = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located(
                            (By.ID, f"poll-option-{i + 1}")
                        )
                    )
                    try:
                        driver.find_element(By.XPATH, '//button[.//span[text()="Add option"]]').click()
                    except NoSuchElementException:
                        pass

                    option_input.send_keys(" ".join(option.split(" ")[1:]))

                # Post poll
                time.sleep(2)
                driver.find_element(By.XPATH, '//button[.//span[text()="Done"]]').click()
                time.sleep(2)
                driver.find_element(By.XPATH, '//button[.//span[text()="Post"]]').click()
                time.sleep(7)

                logger.debug(f"Poll posted in {group_url}")
                wait_for_internet()
                created_polls.append(poll_text)

        except ElementClickInterceptedException:
            logger.error(f"Something went wrong while creating poll: {group_url}")
            return None
        except NoSuchElementException:
            logger.error(f"Poll creation not allowed in group: {group_url}")
            return None
        except TimeoutException:
            logger.error(f"Timeout whil creating poll in group: {group_url}")
            return None

    return created_polls


def scrape_joined_disjoined_unfollwed_groups(group_link: str, group_element_link: str):
    """This function is used to fetch the list of joined as well as disjoined groups.

    Args:
        group_link (str): Group link for the join and disjoin group.
        group_element_link (str): Group element link for the join and disjoin group.

    Returns:
        groups (list): Returns list of groups.
    """
    wait_for_internet()
    driver.get(group_link)
    time.sleep(5)  # Wait for the groups page to load

    unfollowed_groups = []
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        group_elements = driver.find_elements(By.XPATH, group_element_link)

        for element in group_elements:
            group_url = element.get_attribute("href")
            if group_url not in unfollowed_groups:
                unfollowed_groups.append(group_url)

        try:
            load_more_button = driver.find_element(
                By.XPATH, '//button[.//span[text()="Show more results"]]'
            )
            load_more_button.click()
            time.sleep(2)  # Wait for new groups to load after clicking the button
        except:
            pass

        wait_for_internet()
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Wait for new groups to load after scrolling

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    logger.info("Total unjoined groups scraped:", len(unfollowed_groups))
    return unfollowed_groups


def scrape_all_groups():
    """This function combines both joined and unjoined groups URLs.

    Args:
        driver (object): Driver object to load the chrome.

    Returns:
        all_groups (list): Combined list of all groups.
    """
    wait_for_internet()
    joined_groups_link = "https://www.linkedin.com/groups/followed"
    joined_group_ele_link = "//a[contains(@class, 'group-listing-item__title-link-')]"
    joined_groups = scrape_joined_disjoined_unfollwed_groups(
        joined_groups_link, joined_group_ele_link
    )

    time.sleep(6)

    disjoined_groups_link = "https://www.linkedin.com/mynetwork/discovery-see-all/?reasons=List((sourceType%3AGROUP_COHORT%2CreasonContext%3AGROUP_COHORT))"
    disjoined_groups_ele_link = "//a[@class='app-aware-link  discover-entity-type-card__link discover-entity-type-card__link--dash']"
    disjoined_groups = scrape_joined_disjoined_unfollwed_groups(
        disjoined_groups_link, disjoined_groups_ele_link
    )

    all_groups_set = set(joined_groups + disjoined_groups)

    # Create a list with joined_groups first, then the remaining groups from the set
    all_groups = joined_groups + [
        group for group in all_groups_set if group not in joined_groups
    ]
    logger.info("***Length of total groups URL***", len(all_groups), all_groups)
    return all_groups


def append_row_to_csv(file_path: str, headers: list, row: list):
    """This function is used to append a row to CSV file given.

    Args:
        file_path (str): Path of the CSV file
        headers (list): Headers to append in CSV file.
        row (list): ROw to append to CSV file.
    """
    # Check if the file exists
    file_exists = os.path.isfile(file_path)

    # Read existing rows if the file exists
    existing_rows = set()
    if file_exists:
        with open(file_path, mode="r", newline="") as file:
            reader = csv.reader(file)
            for existing_row in reader:
                existing_rows.add(tuple(existing_row))

    # Check if the row already exists in the file
    if tuple(row) in existing_rows:
        logger.info("Row already exists in the CSV file.")
        pass

    # Append the row to the file
    with open(file_path, mode="a", newline="") as file:
        writer = csv.writer(file)
        if not file_exists:
            # Write headers if the file doesn't exist
            writer.writerow(headers)
        writer.writerow(row)
        logger.debug("Row added to the CSV file.")


def main():
    """This is main script function to post a poll into the linkedin groups."""
    wait_for_internet()
    driver.get("https://www.linkedin.com")

    load_cookies(COOKIES_FILE)
    driver.refresh()

    # Login if not already logged in
    if "feed" not in driver.current_url:
        wait_for_internet()
        login()

    time.sleep(5)
    group_urls = scrape_all_groups()  # example group IDs

    start_time = datetime.now()
    for group_url in group_urls[:3]:
        poll_text = create_poll(group_url)

        if poll_text is not None:
            for text in poll_text:
                question = text[0].split(".", 1)[0]
                poll_data = [
                    int("".join(group_url).split("/")[-2]),
                    group_url,
                    int(question),
                ]

                headers = ["Group_ID", "Group_URL", "Question_ID"]
                append_row_to_csv(CSV_FILE, headers, poll_data)

        if datetime.now() - start_time > timedelta(hours=1):
            logger.debug("Pausing for 10 minutes")
            time.sleep(600)
            start_time = datetime.now()

        time.sleep(random.randint(0, 40))  # random delay to avoid being flagged


if __name__ == "__main__":
    main()
