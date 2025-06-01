#!/usr/bin/env python3
import argparse
import logging
from downloader import UnityScraper

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download Xbox cover art & title updates for given Xbox Title IDs "
            "via xboxunity.net. Outputs live under 'unityscrape/{title_id}/...'."
        )
    )
    parser.add_argument(
        "title_ids",
        help=(
            "Comma-separated Title IDs, e.g. '555308C5,00000155'. "
            "Each ID will be processed in turn."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging verbosity (default: INFO).",
    )

    args = parser.parse_args()
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Build a list of trimmed, nonempty Title IDs
    title_ids = [tid.strip() for tid in args.title_ids.split(",") if tid.strip()]
    if not title_ids:
        print("No valid Title IDs provided. Exiting.")
        return

    scraper = UnityScraper()
    failed = scraper.scrape_multiple(title_ids)

    if failed:
        print(f"\nThe following Title IDs failed: {', '.join(failed)}")
    else:
        print("\nAll Title IDs processed successfully.")

if __name__ == "__main__":
    main()
