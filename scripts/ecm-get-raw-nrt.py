
import os
from datetime import datetime, timedelta, UTC

import pandas as pd

from nrt.api.eagleio import EagleIOClient
from nrt.processing import ProcessEagleIOData
from nrt.ecmoorings import ECMoorings
from nrt.aws.aws import CWBAWSS3
from nrt.utils import SITE_LOGGER, IMOSLogging, args_auswaves_processing
from nrt.alerts.email import Email


def generate_general_logger(vargs):

    general_log_file = (
        os.path.join(
            vargs.incoming_path,
            "logs",
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_general_{os.path.basename(__file__).removesuffix('.py')}.log"
            ) # f"{runtime}_general_process.log"
    )

    return IMOSLogging().logging_start(logger_name="general_logger", logging_filepath=general_log_file)

def generate_site_logger(vargs, site):
     
    site_log_file = os.path.join(vargs.incoming_path,
                                    "sites",
                                    site['name'].replace("_",""), 
                                    "logs", 
                                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{site['name'].upper()}_{os.path.basename(__file__).removesuffix(".py")}.log") # f"{runtime}_[CURRENT_SITE]_process.log
    
    return IMOSLogging().logging_start(logger_name="site_logger", logging_filepath=site_log_file)

def load_site_id_parameters(site, ecm_sites, ecm_parameters):
    SITE_ID = ecm_sites.loc[ecm_sites['name'] == site['name'], "site_id"].iloc[0]
    SITE_ECM_PARAMETERS = ecm_parameters[ecm_parameters['site_id'] == SITE_ID]

    return SITE_ID, SITE_ECM_PARAMETERS

def extract_raw():
    SITE_LOGGER.info("EXTRACT RAW DATA ---------------")

    parameters_payload = ECM.create_parameters_payload(SITE_ECM_PARAMETERS)

    start_datetime = datetime.now(UTC) - timedelta(hours=vargs.window)
    end_datetime = datetime.now(UTC) + timedelta(minutes=10)

    SITE_LOGGER.info(f"Extracting data from Eagle.io for the period: {start_datetime} to {end_datetime}")
    raw_data = EAPI.fetch_historic_data(
        params_ids=parameters_payload['ids'],
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        param_ids_pagination=len(parameters_payload['ids']),
        time_pagination=5,
        request_timeout=5,
        max_retries=3,
        logger=SITE_LOGGER
    )
    
    SITE_LOGGER.info("Converting new data to dataframe")
    new_raw_data = ProcessEagleIOData.response_to_dataframe(raw_data)

    SITE_LOGGER.info("Extracting previous data")
    previous_raw_data = extract_previous(start_datetime, end_datetime, site, data_folder="raw_data")


    no_data_code = 0
    if not EAPI.check_new_data(raw_data=new_raw_data):
        log_message = "No data for the desired period. Aborting processing for this site"
        SITE_LOGGER.warning(log_message)
        GENERAL_LOGGER.info(log_message)
        no_data_code = ProcessEagleIOData.NO_DATA_CODES['period']

    if not ProcessEagleIOData.check_previous_new_data(previous_raw_data, new_raw_data):
        log_message = "No new data transmitted since last pipeline execution. Aborting processing for this site"
        SITE_LOGGER.warning(log_message)
        GENERAL_LOGGER.info(log_message)
        no_data_code = ProcessEagleIOData.NO_DATA_CODES['transmission']

    return {
        "previous_raw_data":previous_raw_data,
        "new_raw_data": new_raw_data,
        "no_data_code": no_data_code,
    }

def extract_previous(window_start_time, window_end_date, site, data_folder="raw_data"):

    SITE_LOGGER.info(f"Connecting to AWS S3")
    cwb_s3 = CWBAWSS3(
        aws_access_key_id=os.getenv('AUSWAVES_AWS_S3_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AUSWAVES_AWS_S3_ACCESS_KEY_SECRET'),
        region_name=os.getenv('AUSWAVES_AWS_S3_REGION'),
        bucket=os.getenv('AUSWAVES_AWS_S3_BUCKET'),                        
        prefix=os.getenv('AUSWAVES_AWS_S3_PREFIX'),                        
    )

    SITE_LOGGER.info(f"Generating list of needed csv files from S3 for the period")
    needed_csvs = cwb_s3.generate_needed_files_s3keys(site, window_start_time.date(), window_end_date.date(), vargs.enable_region_folder_structure, data_folder=data_folder)

    # needed_csvs = ['auswaves/vicwaves/Bob/text_archive/2026/04/Bob_20260410.csv', 'auswaves/vicwaves/Bob/text_archive/2026/04/Bob_20260411.csv']

    SITE_LOGGER.info(f"Pulling needed csvs from AWS S3")
    missing_data_errors, previous_data = cwb_s3.get_csvs(needed_csvs)

    if missing_data_errors:
        for error in missing_data_errors:
            SITE_LOGGER.warning(f"No csvs found for: {error['s3Key']}. Error raised: {error['error']}")

    return previous_data  

def transform_raw(data):
    SITE_LOGGER.info("TRANSFORM RAW DATA ---------------")

    SITE_LOGGER.info("Concatenating previous and new data")
    all_raw_data = ProcessEagleIOData.concat_previous_new(data['previous_raw_data'],
                                                          data['new_raw_data'],
                                                          overwrite=False,
                                                          add_new_variable=vargs.add_new_variable,
                                                          raw_data=True)

    SITE_LOGGER.info("Converting time to datetime")
    all_raw_data = ProcessEagleIOData.convert_to_datetime(all_raw_data, old_col="ts", new_col="ts", drop_old=False)

    SITE_LOGGER.info("Splitting raw data into daily dataframes")
    raw_data_daily = ProcessEagleIOData.split_data_daily(all_raw_data)
    
    return raw_data_daily

def load_raw_data(data:dict) -> None:
    SITE_LOGGER.info("LOAD RAW DATA ---------------")

    SITE_LOGGER.info(f"Creating to AWS S3 payload")
    s3_payload_kwargs = {
        'aws_access_key_id': os.getenv('AUSWAVES_AWS_S3_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('AUSWAVES_AWS_S3_ACCESS_KEY_SECRET'),
        'region_name': os.getenv('AUSWAVES_AWS_S3_REGION'),
        'bucket': os.getenv('AUSWAVES_AWS_S3_BUCKET'),
        'prefix': os.getenv('AUSWAVES_AWS_S3_PREFIX')
    }

    s3_payload_loggable = {
        **s3_payload_kwargs,
        "aws_access_key_id": (
            s3_payload_kwargs["aws_access_key_id"][:5] + "****"
            if s3_payload_kwargs["aws_access_key_id"] else None
        ),
        "aws_secret_access_key": "****",
    }

    SITE_LOGGER.info("Connecting to AWS S3",extra={"payload": s3_payload_loggable})    
    cwb_s3 = CWBAWSS3(**s3_payload_kwargs)

    SITE_LOGGER.info("Generating daily csv keys for AWS S3")
    data_daily = cwb_s3.generate_daily_csv_keys(data, site, vargs.enable_region_folder_structure, data_folder="raw_data")

    try:
        for day in data_daily:
            cwb_s3.put_daily_csvs(day)
            SITE_LOGGER.info(f"successfully put file: {day['s3Key']}")

    except Exception as e:
        raise e

if __name__ == "__main__":

    vargs = args_auswaves_processing()

    imos_logging = IMOSLogging()

    GENERAL_LOGGER = generate_general_logger(vargs)

    EAPI = EagleIOClient()
    ECM = ECMoorings()

    BUOYS_METADATA = ECM.load_buoys_metadata()
    ECM_SITES = ECM.load_ecm_sites()
    ECM_PARAMETERS = ECM.load_ecm_parameters()

    sites_error_logs = []

    for idx, site in BUOYS_METADATA.iterrows():
        
        GENERAL_LOGGER.info(f"=========== {site["name"].upper()} processing ===========")
        
        SITE_LOGGER = generate_site_logger(vargs, site)
        SITE_LOGGER.info(f"{site['name'].upper()} processing start")

        try:
            
            SITE_ID, SITE_ECM_PARAMETERS = load_site_id_parameters(site, ECM_SITES, ECM_PARAMETERS)
            
            raw_data = extract_raw()
            
            if isinstance(raw_data['no_data_code'], int) and raw_data['no_data_code'] in ProcessEagleIOData.NO_DATA_CODES.values():
                imos_logging.logging_stop(logger=SITE_LOGGER)
                continue

            raw_data_daily = transform_raw(raw_data)

            load_raw_data(raw_data_daily)
        
            GENERAL_LOGGER.info(f"{site['name'].upper()} processing completed successfully")
            SITE_LOGGER.info(f"{site['name'].upper()} processing completed successfully")

            site_logger_file_path = imos_logging.get_log_file_path(SITE_LOGGER)
            imos_logging.logging_stop(logger=SITE_LOGGER)

        except Exception as e:
            error_message = IMOSLogging().unexpected_error_message.format(site_name=site['name'].upper())
            GENERAL_LOGGER.error(str(e), exc_info=True)
            SITE_LOGGER.error(str(e), exc_info=True)
        
            # Closing current site logging
            site_logger_file_path = imos_logging.get_log_file_path(SITE_LOGGER)
            imos_logging.logging_stop(logger=SITE_LOGGER)
            error_logger_file_path = imos_logging.rename_log_file_if_error(site_name=site['name'],
                                                                           file_path=site_logger_file_path,
                                                                            script_name=os.path.basename(__file__).removesuffix(".py"),
                                                                            add_runtime=False)
            sites_error_logs.append(error_logger_file_path)

    if sites_error_logs:
        if vargs.email_alert:
            e = Email(script_name=os.path.basename(__file__),
                    email=os.getenv("EMAIL_TO"),
                    log_file_path=sites_error_logs)
            e.send()

        
    


