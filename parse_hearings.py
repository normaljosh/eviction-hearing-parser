"""
Module to get case details given case numbers.
To perform a scraper run, use: python parse_hearings.py name_of_csv_with_case_numbers
"""

import csv
import click
import fetch_page
import logging
import sys
import simplejson

from scrapers import BaseScraper
from typing import Any, Dict, List, Optional
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


def parse_all_from_parse_filings(
    case_nums: List[str],
    county: str,
    test_scraper: Optional[BaseScraper] = None,
    showbrowser: bool = False,
    json: bool = True,
    db: bool = True,
) -> List[Dict[str, Any]]:
    """
    Gets case details for each case number in `case_nums` and sends the data to PostgreSQL.
    Logs any case numbers for which getting data failed.
    """

    scraper_map = {
                    'travis' : fetch_page.Scraper(),
                    'williamson' : fetch_page.WilliamsonScraper()
                    }


    if not test_scraper:
        test_scraper = scraper_map[county.lower()]

    parsed_cases = []
    for tries in range(1, 6):
        try:
            parsed_cases = test_scraper.make_case_list(case_nums)
            break
        except Exception as e:
            logger.error(
                f"Failed to parse hearings on attempt {tries}. Error message: {e}"
            )

    if db:
        import persist

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

@click.argument("county", type=click.STRING, default="travis")

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
def parse_all(infile, outfile, county, showbrowser=False, json=True, db=True):
    """Same as `parse_all_from_parse_filings()` but takes in a csv of case numbers instead of a list."""

    ids_to_parse = get_ids_to_parse(infile)
    parsed_cases = parse_all_from_parse_filings(
        case_nums=ids_to_parse, showbrowser=showbrowser, db=db, county=county
    )
    if json:
        simplejson.dump(parsed_cases, outfile)


if __name__ == "__main__":
    parse_all()
