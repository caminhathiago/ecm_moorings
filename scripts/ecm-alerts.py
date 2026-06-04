
import os
from datetime import datetime, timedelta, UTC

import pandas as pd

from nrt.api.eagleio import EagleIOClient
from nrt.processing import ProcessEagleIOData
from nrt.ecmoorings import ECMoorings
from nrt.aws.aws import CWBAWSS3
from nrt.utils import SITE_LOGGER, IMOSLogging, args_auswaves_processing
from nrt.alerts.email import Email, EmailAlerts
from nrt.alerts.alerts import GeofenceAlert, TimefenceAlert, BatteryVoltageAlert


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

def extract_raw():
    SITE_LOGGER.info("EXTRACT RAW DATA ---------------")

    # parameters_payload = ECM.create_parameters_payload(SITE_ECM_PARAMETERS)

    start_datetime = datetime.now(UTC) - timedelta(hours=vargs.window)
    end_datetime = datetime.now(UTC) + timedelta(minutes=10)


    SITE_LOGGER.info("Extracting previous data")
    raw_data = extract_previous(start_datetime, end_datetime, site, data_folder="raw_data")

    no_data_code = 0

    return {
        "raw_data":raw_data,
        # "new_raw_data": new_raw_data,
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

def evaluate_alerts(raw_data):


    geofence_results = (
        GeofenceAlert(
            site_name=site['name'],
            lat=site['DeployLat'],
            lon=site['DeployLon'],
            search_rad=site['search_rad'],
        ).evaluate(raw_data['raw_data'])
    )
    
    
    timefence_results = (
        TimefenceAlert(
            site_name=site['name'],
            max_gap_hours=site['time_cutoff'],
        ).evaluate(raw_data['raw_data'])
    )

    battery_results = (
        BatteryVoltageAlert(
            site_name=site['name'],
            min_voltage=10.0,
        ).evaluate(raw_data['raw_data'])
    )

    return {
        "geofence_alert": geofence_results,
        "timefence_alert": timefence_results,
        "battery_voltage_alert": battery_results
    }

def notify(alerts_results, site):
    
    for alert_type, alert_event in alerts_results.items():
        
        if alert_event.triggered and site['send_alert_emails']:
            SITE_LOGGER.warning(f"{alert_type} triggered: {alert_event.message}")
            SITE_LOGGER.info(f"Sending email alert to: {site['alert_emails']}")
            EmailAlerts(
                    email_to=site['alert_emails'],
                    email_from=os.getenv("EMAIL_FROM"),
                    ).send(alert_event)
    
        else:
            SITE_LOGGER.info(f"{alert_type} not triggered.")

if __name__ == "__main__":

    vargs = args_auswaves_processing()

    imos_logging = IMOSLogging()

    GENERAL_LOGGER = generate_general_logger(vargs)

    EAPI = EagleIOClient()
    ECM = ECMoorings()

    BUOYS_METADATA = ECM.load_buoys_metadata()

    sites_error_logs = []

    for idx, site in BUOYS_METADATA.iterrows():

        GENERAL_LOGGER.info(f"{site['name'].upper()} alerts ===========")
        
        SITE_LOGGER = generate_site_logger(vargs, site)
        SITE_LOGGER.info(f"{site['name'].upper()} processing start")

        try:
            
            raw_data = extract_raw()

            if isinstance(raw_data['no_data_code'], int) and raw_data['no_data_code'] in ProcessEagleIOData.NO_DATA_CODES.values():
                imos_logging.logging_stop(logger=SITE_LOGGER)
                continue

            alerts_results = evaluate_alerts(raw_data)

            notify(alerts_results, site)

            GENERAL_LOGGER.info(f"{site['name'].upper()} alerts evaluation completed")
            SITE_LOGGER.info(f"{site['name'].upper()} alerts evaluation completed")

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