"""
Module to get case details given case numbers.
To perform a scraper run, use: python parse_hearings.py name_of_csv_with_case_numbers
"""

import csv
import os
import click
import hearing
import fetch_page
import persist
import logging
import sys
import simplejson
from typing import Any, Dict, List
from emailing import log_and_email

logger = logging.getLogger()
logging.basicConfig(stream=sys.stdout)
logger.setLevel(logging.INFO)


def get_ids_to_parse(infile: click.File) -> List[str]:
    """Gets a list of case numbers from the csv `infile`"""

    ids_to_parse = []
    reader = csv.reader(infile)
    for row in reader:
        ids_to_parse.append(row[0])
    return ids_to_parse


REAL_SCRAPER = fetch_page.Scraper()


def make_case_list(
    ids_to_parse: List[str], scraper=REAL_SCRAPER
) -> List[Dict[str, Any]]:
    """Gets case details for each case number in `ids_to_pars`"""

    parsed_cases, failed_ids = [], []
    for id_to_parse in ids_to_parse:
        new_case = scraper.fetch_parsed_case(id_to_parse)
        if new_case:
            parsed_cases.append(new_case)
        else:
            failed_ids.append(id_to_parse)

    if failed_ids:
        error_message = f"Failed to scrape data for {len(failed_ids)} case numbers. Here they are:\n{', '.join(failed_ids)}"
        log_and_email(error_message, "Failed Case Numbers", error=True)

    return parsed_cases


def parse_all_from_parse_filings(
    case_nums: List[str],
    showbrowser: bool = False,
    json: bool = True,
    db: bool = True,
    scraper=REAL_SCRAPER,
) -> List[Dict[str, Any]]:
    """
    Gets case details for each case number in `case_nums` and sends the data to PostgreSQL.
    Logs any case numbers for which getting data failed.
    """

    if showbrowser:
        from selenium import webdriver

        fetch_page.driver = webdriver.Chrome("./chromedriver")

    parsed_cases = []
    for tries in range(1, 6):
        try:
            parsed_cases = make_case_list(case_nums, scraper=scraper)
            break
        except Exception as e:
            logger.error(
                f"Failed to parse hearings on attempt {tries}. Error message: {e}"
            )

    if db:
        logger.info(
            f"Finished making case list, now will send all {len(parsed_cases)} cases to SQL."
        )

        failed_cases = []
        for parsed_case in parsed_cases:
            try:
                persist.rest_case(parsed_case)
            except:
                try:
                    failed_cases.append(parsed_case["case_number"])
                except:
                    logger.error(
                        "A case failed to be parsed but it doesn't have a case number."
                    )

        if failed_cases:
            error_message = f"Failed to send the following case numbers to SQL:\n{', '.join(failed_cases)}"
            log_and_email(
                error_message,
                "Case Numbers for Which Sending to SQL Failed",
                error=True,
            )
        logger.info("Finished sending cases to SQL.")

    return parsed_cases


@click.command()
@click.argument(
    "infile", type=click.File(mode="r"),
)
@click.argument("outfile", type=click.File(mode="w"), default="result.json")
@click.option(
    "--showbrowser / --headless",
    default=False,
    help="whether to operate in headless mode or not",
)
@click.option(
    "--json / --no-json", default=True, help="whether to dump JSON or not",
)
@click.option(
    "--db / --no-db", default=True, help="whether to persist the data to a db",
)
def parse_all(infile, outfile, showbrowser=False, json=True, db=True):
    """Same as `parse_all_from_parse_filings()` but takes in a csv of case numbers instead of a list."""

    # If showbrowser is True, use the default selenium driver
    if showbrowser:
        from selenium import webdriver

        fetch_page.driver = webdriver.Chrome("./chromedriver")

    ids_to_parse = get_ids_to_parse(infile)
    parsed_cases = parse_all_from_parse_filings(
        case_nums=ids_to_parse, showbrowser=showbrowser, db=db
    )
    if json:
        simplejson.dump(parsed_cases, outfile)


if __name__ == "__main__":
    parse_all()
