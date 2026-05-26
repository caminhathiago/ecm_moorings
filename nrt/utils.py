import os
import sys
from datetime import datetime, timezone
import logging
import re
import argparse

import pickle
# from netCDF4 import Dataset
import pandas as pd
import numpy as np
from dotenv import load_dotenv, parser


GENERAL_LOGGER = logging.getLogger("general_logger")
SITE_LOGGER = logging.getLogger("site_logger")

load_dotenv()

def args_processing():
    """
    Returns the script arguments

        Parameters:

        Returns:
            vargs (obj): input arguments
    """
    parser = argparse.ArgumentParser(description='Creates NetCDF files.\n '
                                     'Prints out the path of the new locally generated NetCDF file.')
    
    parser.add_argument('-o', '--output-path', dest='output_path', type=str, default=None,
                        help="output directory of netcdf file",
                        required=True)
    
    parser.add_argument('-i', '--incoming-path', dest='incoming_path', type=str, default=None,
                        help="directory to store netcdf file to be pushed to AODN",
                        required=True)

    parser.add_argument('-w', '--window', dest='window', type=str, default=24,
                        help="desired window from present backwards to be processed and qualified. Default to 24, please check argument --window-unit for the right desired unit.",
                        required=False)

    parser.add_argument('-wu', '--window-unit', dest='window_unit', type=str, default="hours",
                        help="desired window unit (hours:Default, months).",
                        required=False)

    parser.add_argument('-bfw', '--backfill-wb-log', dest='backfill_wb_log', type=str, default=None, nargs=1,
                        help="Deployment datetimes period to be processed. Please pass start and end dates as YYYYmmddTHHMMSS",
                        required=False)

    def parse_site_list(value):
        return [site.strip() for site in value.split(',') if site.strip()]

    parser.add_argument(
        '-sp', '--site-to-process',
        dest='site_to_process',
        type=parse_site_list,
        default=None,
        help="Comma-separated list of sites to be processed (e.g., site1,site2,site3). A single site is also valid.",
        required=False
    )

    parser.add_argument('-pp', '--period-to-process', dest='period_to_process', type=str, default=None, nargs=2,
                        help="desired period to be extracted, processed and qualified. Please pass start and end dates as YYYY-mm-ddTHH:MM separated by a blank space.",
                        required=False)
    
    parser.add_argument('-pqc', '--period-to-qualify', dest='period_to_qualify', type=str, default=None, nargs=2,
                        help="desired period to be qualified. Please pass start and end dates as YYYY-mm-ddTHH:MM separated by a blank space.",
                        required=False)

    parser.add_argument('-bf', '--backfill', dest='backfill', action="store_true",
                        help="wether the user wants to backfill the data from the latest available time back to the last processed time.",
                        required=False)
    
    parser.add_argument('-fpn', '--flag-previous-new', dest='flag_previous_new', action="store_true",
                        help="wether the user wants to flag previous/new data in the data products generated",
                        required=False)
    
    parser.add_argument('-e', '--email-alert', dest='email_alert', action="store_true",
                        help="toggle email alert.",
                        required=False)

    # parser.add_argument('-p', '--push-to-incoming', dest='incoming_path', type=str, default=None,
    #                     help="incoming directory for files to be ingested by AODN pipeline (Optional)",
    #                     required=False)
    

    
    vargs = parser.parse_args()

    # if vargs.output_path is None:
    #     vargs.output_path = tempfile.mkdtemp()
    
    if not os.path.exists(vargs.output_path):
        try:
            os.makedirs(vargs.output_path)
        except Exception:
            raise ValueError('{path} not a valid path'.format(path=vargs.output_path))
            sys.exit(1)

    if not os.path.exists(vargs.incoming_path):
        try:
            os.makedirs(vargs.incoming_path)
        except Exception:
            raise ValueError('{path} not a valid path'.format(path=vargs.incoming_path))
            sys.exit(1)

    if vargs.period_to_process:
        vargs.period_to_process = vargs.period_to_process.split()
        vargs.period_to_process_start_date = datetime.strptime(vargs.period_to_process[0],"%Y-%m-%dT%H:%M")
        vargs.period_to_process_end_date = datetime.strptime(vargs.period_to_process[1],"%Y-%m-%dT%H:%M")

    if vargs.period_to_qualify:
        vargs.period_to_qualify = vargs.period_to_qualify.split()
        vargs.period_to_qualify_start_date = datetime.strptime(vargs.period_to_qualify[0],"%Y-%m-%dT%H:%M")
        vargs.period_to_qualify_end_date = datetime.strptime(vargs.period_to_qualify[1],"%Y-%m-%dT%H:%M")

    if vargs.backfill:
        backfill = True
    else:
        backfill = False

    if vargs.flag_previous_new:
        flag_previous_new = True
    else:
        flag_previous_new = False

    if vargs.email_alert:
        vargs.email_alert = True
    else:
        vargs.email_alert = False

    if vargs.backfill_wb_log:
        vargs.backfill_wb_log = datetime.strptime(vargs.backfill_wb_log[0],"%Y%m%dT%H%M%S")

    return vargs

def args_auswaves_processing():
    """
    Returns the script arguments

        Parameters:

        Returns:
            vargs (obj): input arguments
    """
    parser = argparse.ArgumentParser(description='Creates NetCDF files.\n '
                                     'Prints out the path of the new locally generated NetCDF file.')
    
    parser.add_argument('-o', '--output-path', dest='output_path', type=str, default=None,
                        help="output directory of netcdf file",
                        required=True)
    
    parser.add_argument('-i', '--incoming-path', dest='incoming_path', type=str, default=None,
                        help="directory to store netcdf file to be pushed to AODN",
                        required=True)

    parser.add_argument('-w', '--window', dest='window', type=str, default=24,
                        help="desired window from present backwards to be processed and qualified. Default to 24, please check argument --window-unit for the right desired unit.",
                        required=False)

    parser.add_argument('-wu', '--window-unit', dest='window_unit', type=str, default="hours",
                        help="desired window unit (hours:Default, months).",
                        required=False)

    parser.add_argument('-bfw', '--backfill-wb-log', dest='backfill_wb_log', type=str, default=None, nargs=1,
                        help="Deployment datetimes period to be processed. Please pass start and end dates as YYYYmmddTHHMMSS",
                        required=False)

    parser.add_argument('-eq', '--enable-qualification', dest='enable_qualification', action='store_true',
                    help="Enable qualification based on QARTOD manuals.")

    def parse_site_list(value):
        return [site.strip() for site in value.split(',') if site.strip()]

    parser.add_argument(
        '-sp', '--site-to-process',
        dest='site_to_process',
        type=parse_site_list,
        default=None,
        help="Comma-separated list of sites to be processed (e.g., site1,site2,site3). A single site is also valid.",
        required=False
    )

    parser.add_argument('-pp', '--period-to-process', dest='period_to_process', type=str, default=None, nargs=2,
                        help="desired period to be extracted, processed and qualified. Please pass start and end dates as YYYY-mm-ddTHH:MM separated by a blank space.",
                        required=False)
    
    parser.add_argument('-pqc', '--period-to-qualify', dest='period_to_qualify', type=str, default=None, nargs=2,
                        help="desired period to be qualified. Please pass start and end dates as YYYY-mm-ddTHH:MM separated by a blank space.",
                        required=False)

    parser.add_argument('-bf', '--backfill', dest='backfill', action="store_true",
                        help="wether the user wants to backfill the data from the latest available time back to the last processed time.",
                        required=False)
    
    parser.add_argument('-fpn', '--flag-previous-new', dest='flag_previous_new', action="store_true",
                        help="wether the user wants to flag previous/new data in the data products generated",
                        required=False)
    
    parser.add_argument('-e', '--email-alert', dest='email_alert', action="store_true",
                        help="toggle email alert.",
                        required=False)

    # parser.add_argument('-p', '--push-to-incoming', dest='incoming_path', type=str, default=None,
    #                     help="incoming directory for files to be ingested by AODN pipeline (Optional)",
    #                     required=False)

    parser.add_argument('-ow', '--overwrite', dest='overwrite', action="store_true",
                        help="toggle on overwritting of previous data",
                        required=False)

    parser.add_argument('-anv', '--add-new-variable', dest='add_new_variable', action="store_true",
                        help="Allow adding new variables in the new data that are not present in the previous data when concatenating them.",
                        required=False)

    
    vargs = parser.parse_args()

    # if vargs.output_path is None:
    #     vargs.output_path = tempfile.mkdtemp()
    
    if not os.path.exists(vargs.output_path):
        try:
            os.makedirs(vargs.output_path)
        except Exception:
            raise ValueError('{path} not a valid path'.format(path=vargs.output_path))
            sys.exit(1)

    if not os.path.exists(vargs.incoming_path):
        try:
            os.makedirs(vargs.incoming_path)
        except Exception:
            raise ValueError('{path} not a valid path'.format(path=vargs.incoming_path))
            sys.exit(1)

    if vargs.period_to_process:
        vargs.period_to_process = vargs.period_to_process.split()
        vargs.period_to_process_start_date = datetime.strptime(vargs.period_to_process[0],"%Y-%m-%dT%H:%M")
        vargs.period_to_process_end_date = datetime.strptime(vargs.period_to_process[1],"%Y-%m-%dT%H:%M")

    if vargs.period_to_qualify:
        vargs.period_to_qualify = vargs.period_to_qualify.split()
        vargs.period_to_qualify_start_date = datetime.strptime(vargs.period_to_qualify[0],"%Y-%m-%dT%H:%M")
        vargs.period_to_qualify_end_date = datetime.strptime(vargs.period_to_qualify[1],"%Y-%m-%dT%H:%M")

    if vargs.backfill:
        backfill = True
    else:
        backfill = False

    if vargs.flag_previous_new:
        flag_previous_new = True
    else:
        flag_previous_new = False

    if vargs.email_alert:
        vargs.email_alert = True
    else:
        vargs.email_alert = False

    if vargs.add_new_variable:
        vargs.add_new_variable = True
    else:
        vargs.add_new_variable = False

    if vargs.backfill_wb_log:
        vargs.backfill_wb_log = datetime.strptime(vargs.backfill_wb_log[0],"%Y%m%dT%H%M%S")

    return vargs

def args_pushing():
    parser = argparse.ArgumentParser(description="pushes files to AODN FTP server. ")
    
    parser.add_argument('-o', '--output-path', dest='output_path', type=str, default=None,
                        help="output directory of netcdf file",
                        required=True)
    
    parser.add_argument('-i', '--incoming-path', dest='incoming_path', type=str, default=None,
                        help="directory to store netcdf file to be pushed to AODN",
                        required=True)
    
    parser.add_argument('-lh', '--lookback-hours', dest='lookback_hours', type=str, default=1,
                        help="desired window from present backwards to be processed and qualified. Default to 24, please check argument --window-unit for the right desired unit.",
                        required=False)

    parser.add_argument('-e', '--email-alert', dest='email_alert', action="store_true",
                        help="toggle email alert.",
                        required=False)

    vargs = parser.parse_args()

    if not os.path.exists(vargs.output_path):
        try:
            os.makedirs(vargs.output_path)
        except Exception:
            raise ValueError('{path} not a valid path'.format(path=vargs.output_path))
            sys.exit(1)

    if not os.path.exists(vargs.incoming_path):
        try:
            os.makedirs(vargs.incoming_path)
        except Exception:
            raise ValueError('{path} not a valid path'.format(path=vargs.incoming_path))
            sys.exit(1)

    if vargs.email_alert:
        vargs.email_alert = True
    else:
        vargs.email_alert = False

    vargs.lookback_hours = int(vargs.lookback_hours)

    return vargs


class IMOSLogging:
    unexpected_error_message = "An unexpected error occurred when processing {site_name}\n Please check the site log for details"

    def __init__(self):
        pass

    def logging_start(self, logging_filepath, logger_name="general_logger", level=logging.INFO):
        """
        Start logging using the Python logging library.
        Parameters:
            logger_name (str): Name of the logger to create or retrieve.
            level (int): Logging level (default: logging.INFO).
        Returns:
            logger (logging.Logger): Configured logger instance.
        """
        self.logging_filepath = logging_filepath

        if not os.path.exists(os.path.dirname(self.logging_filepath)):
            os.makedirs(os.path.dirname(self.logging_filepath))

        self.logger = logging.getLogger(logger_name)

        if not self.logger.hasHandlers():
            # self.logger.setLevel(level)

            # handler = logging.FileHandler(self.logging_filepath, mode="w")
            # handler.setLevel(level)

            # formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            # handler.setFormatter(formatter)

            # self.logger.addHandler(handler)

            self.logger.setLevel(level)

            # File handler (writes to file)
            file_handler = logging.FileHandler(self.logging_filepath, mode="w")
            file_handler.setLevel(level)

            # Stream handler (prints to CLI)
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setLevel(level)

            # Formatter
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            stream_handler.setFormatter(formatter)

            # Add both handlers
            self.logger.addHandler(file_handler)
            self.logger.addHandler(stream_handler)

        return self.logger

    def logging_stop(self, logger):
        """Close logging handlers for the current logger."""
        handlers = list(logger.handlers)
        for handler in handlers:
            logger.removeHandler(handler)
            handler.flush()
            handler.close()

    def get_log_file_path(self, logger):
        return logger.handlers[0].baseFilename
    
    def rename_log_file_if_error(self, site_name: str, file_path, script_name: str, add_runtime: bool = True):
        site_name = site_name.upper()
        runtime = datetime.now().strftime("%Y%m%dT%H%M%S")
        pattern = f"{site_name}_{script_name}"
        new_name = "ERROR_" + f"{site_name}_{script_name}"
        if add_runtime:
            new_name += f"_{runtime}"

        new_file_name = re.sub(pattern, new_name, file_path)
        if os.path.exists(new_file_name):
            os.replace(file_path, new_file_name)
        else:
            os.rename(file_path, new_file_name)
        GENERAL_LOGGER.info(f"{site_name} log file renamed as {new_file_name}")

        return os.path.join(file_path, new_file_name)

    def rename_push_log_if_error(self, file_path: str, add_runtime: bool = True):
        runtime = datetime.now().strftime("%Y%m%dT%H%M%S")
        pattern = "aodn_ftp_push"
        new_name = f"ERROR_aodn_ftp_push"
        if add_runtime:
            new_name += f"_{runtime}"

        new_file_name = re.sub(pattern, new_name, file_path)
        if os.path.exists(new_file_name):
            os.replace(file_path, new_file_name)
        else:
            os.rename(file_path, new_file_name)

        return os.path.join(file_path, new_file_name)

class generalTesting:
    
    @staticmethod
    def generate_pickle_file(data, file_name: str, site_name: str):
        file_path = f"tests/pickle_files/{site_name}_{file_name}.pkl"
        with open(file_path, "wb") as pickle_file:
            pickle.dump(data, pickle_file)
            print(f"saved pkl as {file_path}")
    
    @staticmethod
    def open_pickle_file(file_name: str):
        file_path = f"tests/pickle_files/{file_name}.pkl"
        with open(file_path, "rb") as pickle_file:
            data = pickle.load(pickle_file)
            print(f"openned pkl as {file_path}")
        return data
    

class FilesHandler():
    def __init__(self):
        pass

    def _get_file_path(self, file_name: str, file_path: str = os.getenv('FILES_PATH')):
        if os.path.exists(os.path.join(file_path, file_name)):
            # print(os.path.join(file_path, file_name))
            return os.path.join(file_path, file_name)
        else:
            error_message = f"""Path for {file_name} does not exist.\nCheck if the correct path was provided, or if {file_name} was moved."""
            print(error_message)
            GENERAL_LOGGER.error(error_message)
            raise FileNotFoundError(error_message)
        

class csvOutput:
    
    @staticmethod
    def extract_monthly_date(data:pd.DataFrame) -> list[pd.DataFrame]:
        
        time_col = [col for col in data.columns if "TIME" in col][0]
        
        periods = (pd.to_datetime(data[time_col])
                   .dt.to_period("M")
                   .unique()
                )

        dataframes = []
        for period in periods:
            mask = data[time_col].dt.to_period("M") == period
            monthly_df = data.loc[mask]
            dataframes.append((period, monthly_df))

        return dataframes

    @staticmethod
    def format_period(period: pd.PeriodIndex) -> str:
        return str(period).replace("-","") + "01"

    @staticmethod
    def save_csv(file_path: str, site_name:str, file_name_preffix: str, data: pd.DataFrame) -> None:
        
        dataframes = csvOutput.extract_monthly_date(data)        
        
        site_name_processed = site_name.replace("_", "")
        output_path = os.path.join(file_path, "sites", site_name_processed, "csv")
        if not os.path.isdir(output_path):
            os.makedirs(output_path)

        for dataframe in dataframes:
            period_str = csvOutput.format_period(dataframe[0])
            file_name = period_str + "_" + site_name.upper() + file_name_preffix
            file_output_path = os.path.join(output_path, file_name)
            data.reset_index().to_csv(file_output_path, index=False)
            SITE_LOGGER.info(f"file saved as {output_path}")
        

