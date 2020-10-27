#!/usr/bin/env python3

# library imports
import argparse
import logging
import sys
import pathlib

# third party imports
from warcio.capture_http import capture_http
import requests  # requests must be imported after capture_http
import arrow
import attr
import logging_tree

# self imports
from playstation_store_2020_oct_scrape import scrape
from playstation_store_2020_oct_scrape import warcio_scrape


class ArrowLoggingFormatter(logging.Formatter):
    ''' logging.Formatter subclass that uses arrow, that formats the timestamp
    to the local timezone (but its in ISO format)
    '''

    def formatTime(self, record, datefmt=None):
        return arrow.get("{}".format(record.created), "X").to("local").isoformat()


def isValidNewFileLocation(filePath):
    ''' see if the file path given to us by argparse is a file
    @param filePath - the filepath we get from argparse
    @return the filepath as a pathlib.Path() if it is a file, else we raise a ArgumentTypeError'''

    path_maybe = pathlib.Path(filePath)
    path_resolved = None

    # try and resolve the path
    try:
        path_resolved = path_maybe.resolve(strict=False).expanduser()

    except Exception as e:
        raise argparse.ArgumentTypeError("Failed to parse `{}` as a path: `{}`".format(filePath, e))

    if not path_resolved.parent.exists():
        raise argparse.ArgumentTypeError("The parent directory of  `{}` doesn't exist!".format(path_resolved))

    return path_resolved


def isFileType(strict=True):
    def _isFileType(filePath):
        ''' see if the file path given to us by argparse is a file
        @param filePath - the filepath we get from argparse
        @return the filepath as a pathlib.Path() if it is a file, else we raise a ArgumentTypeError'''

        path_maybe = pathlib.Path(filePath)
        path_resolved = None

        # try and resolve the path
        try:
            path_resolved = path_maybe.resolve(strict=strict).expanduser()

        except Exception as e:
            raise argparse.ArgumentTypeError("Failed to parse `{}` as a path: `{}`".format(filePath, e))

        # double check to see if its a file
        if strict:
            if not path_resolved.is_file():
                raise argparse.ArgumentTypeError("The path `{}` is not a file!".format(path_resolved))

        return path_resolved
    return _isFileType

def isDirectoryType(filePath):
    ''' see if the file path given to us by argparse is a directory
    @param filePath - the filepath we get from argparse
    @return the filepath as a pathlib.Path() if it is a directory, else we raise a ArgumentTypeError'''

    path_maybe = pathlib.Path(filePath)
    path_resolved = None

    # try and resolve the path
    try:
        path_resolved = path_maybe.resolve(strict=True).expanduser()

    except Exception as e:
        raise argparse.ArgumentTypeError("Failed to parse `{}` as a path: `{}`".format(filePath, e))

    # double check to see if its a file
    if not path_resolved.is_dir():
        raise argparse.ArgumentTypeError("The path `{}` is not a file!".format(path_resolved))

    return path_resolved

if __name__ == "__main__":
    # if we are being run as a real program

    parser = argparse.ArgumentParser(
        description="scrape the playstation games site",
        epilog="Copyright 2020-10-24 - Mark Grandi",
        fromfile_prefix_chars='@')

    parser.add_argument("--log-to-file-path", dest="log_to_file_path", type=isFileType(False), help="log to the specified file")
    parser.add_argument("--verbose", action="store_true", help="Increase logging verbosity")


    subparsers = parser.add_subparsers(help="sub-command help" )

    scrape_urls_parser = subparsers.add_parser("scrape_urls", help="Scrape URLs to JSON")
    scrape_urls_parser.add_argument('--outfile', dest="outfile", required=True, type=isValidNewFileLocation, help="where to save the JSON file containing the URLs")
    scrape_urls_parser.set_defaults(func_to_run=scrape.get_games_list)


    wpull_parser = subparsers.add_parser("wpull_urls", help="download URLs with wpull")
    wpull_parser.add_argument("--url-list", dest="url_list", required=True, type=isFileType(), help="the list of urls to download")
    wpull_parser.add_argument("--wpull-binary", dest="wpull_binary", required=True, type=isFileType(), help="the path to wpull")
    wpull_parser.add_argument("--warc-output-folder", dest="warc_output_folder", required=True, type=isDirectoryType, help="where to store the resulting WARCs")
    wpull_parser.set_defaults(func_to_run=scrape.wpull_games_list)


    warcio_parser = subparsers.add_parser("warcio_scrape", help="download urls via warcio")
    warcio_parser.add_argument("--sku-list", dest="sku_list", required=True, type=isFileType(), help="the list of skus to download")
    warcio_parser.add_argument("--region-lang", dest="region_lang", required=True, help="the first part of a region code, aka the `en` in `en-US`")
    warcio_parser.add_argument("--region-country", dest="region_country", required=True, help="the second part of a region code, aka the `us` in `en-US`")
    warcio_parser.add_argument("--warc-output-file", dest="warc_output_file", type=isFileType(False),
        help="where to save the warc file, include 'warc.gz' in this name please")
    warcio_parser.add_argument("--media-files-output-file", dest="media_files_output_file", type=isFileType(False),
        help="where to save the list of media urls we discovered")
    warcio_parser.set_defaults(func_to_run=warcio_scrape.do_warcio_scrape)


    try:
        parsed_args = parser.parse_args()

        # set up logging stuff
        logging.captureWarnings(True) # capture warnings with the logging infrastructure
        root_logger = logging.getLogger()
        logging_formatter = ArrowLoggingFormatter("%(asctime)s %(threadName)-10s %(name)-20s %(levelname)-8s: %(message)s")

        if parsed_args.log_to_file_path:

            file_handler = logging.FileHandler(parsed_args.log_to_file_path, encoding="utf-8")
            file_handler.setFormatter(logging_formatter)
            root_logger.addHandler(file_handler)

        else:
            logging_handler = logging.StreamHandler(sys.stdout)
            logging_handler.setFormatter(logging_formatter)
            root_logger.addHandler(logging_handler)


        # set logging level based on arguments
        if parsed_args.verbose:
            root_logger.setLevel("DEBUG")
        else:
            root_logger.setLevel("INFO")



        root_logger.debug("Parsed arguments: %s", parsed_args)
        root_logger.debug("Logger hierarchy:\n%s", logging_tree.format.build_description(node=None))


        # run the function associated with each sub command
        if "func_to_run" in parsed_args:

            parsed_args.func_to_run(parsed_args)

        else:
            root_logger.info("no subcommand specified!")
            parser.print_help()
            sys.exit(0)

        root_logger.info("Done!")
    except Exception as e:
        root_logger.exception("Something went wrong!")
        sys.exit(1)