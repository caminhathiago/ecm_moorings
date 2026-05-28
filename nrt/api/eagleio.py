import os
import time
import random
import json
from datetime import datetime, timedelta, UTC
import logging

import requests
from dotenv import load_dotenv
import pandas as pd

# from nrt.aws.aws import CWBAWSS3
# from nrt.utils import args_auswaves_processing, IMOSLogging



load_dotenv()

class EagleIOClient:
    
    def __init__(self, api_key: str=None, base_url: str = "https://api.eagle.io/api/v1/"):
        
        if not api_key:
            self.api_key = os.getenv("EAGLE_API_KEY")
        else:        
            self.api_key = api_key

        self.base_url = base_url

    def paginate_request_param_ids(self, param_ids:list, page_size:int=1):
        for i in range(0, len(param_ids), page_size):
            yield param_ids[i:i + page_size]

    def paginate_request_time(self, start:datetime, end:datetime, step_hours=1, page_limit:int=10):
        
        page_count = 0
        
        while start < end:
            
            page_count += 1

            if page_count > page_limit:
                raise Exception(f"Pagination limit of {page_limit} pages reached, aborting request.")

            next_end = min(start + timedelta(hours=step_hours), end)
            yield start, next_end
            start = next_end

    def retry_setup(self, attempt:int, max_retries:int, logger: logging.Logger, error_type:str) -> None:

        errors = ("Timeout", "413")
        if error_type not in errors:
            raise ValueError(f"error type not valid, must be {errors}.")

        if error_type == "Timeout":
            log_message_prefix = "Timeout"
        elif error_type == "413":
            log_message_prefix = "413 received"

        sleep = min(60, (2 ** attempt) + random.uniform(0, 1))

        logger.warning(
            f"{log_message_prefix} (attempt {attempt}/{max_retries}). "
            f"Retrying in {sleep:.1f}s"
        )

        time.sleep(sleep)

    def fetch_historic_data(
        self,
        params_ids: list[str],
        start_datetime: datetime=datetime.now(UTC)-timedelta(hours=24),
        end_datetime: datetime=datetime.now(UTC),
        time_pagination: int=1,
        time_pagination_limit: int=10,
        param_ids_pagination: int=1,
        request_timeout: int=5,
        max_retries: int=3,
        logger: logging.Logger=None
    ):

        logger = logger or NoOpLogger()

        headers = {
            "X-API-Key": self.api_key
        }

        endpoint = "historic/"
       
        results = []
        time_page_count = 0
        for t0, t1 in self.paginate_request_time(start_datetime,
                                                 end_datetime, 
                                                 step_hours=time_pagination,
                                                 page_limit=time_pagination_limit):
            
            time_page_count += 1
            logger.info(f"Time page: {time_page_count}")
            logger.info(f"{t0} to {t1}")
            
            params_page_count = 0
            for param_ids_page in self.paginate_request_param_ids(params_ids, param_ids_pagination):

                params_page_count += 1
                logger.info(f"Params page: {params_page_count}")
                # logger.info(f"Param IDs: {','.join(param_ids_page)}")
                
                args = {
                    "startTime": t0.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "endTime": t1.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "params": ",".join(param_ids_page)
                }
                
                response = None
                errors = {}
                for attempt in range(1,max_retries+1):

                    try:
                        response = requests.get(
                            self.base_url + endpoint,
                            headers=headers,
                            params=args,
                            timeout=request_timeout
                        )
                    except requests.exceptions.Timeout as e:
                        errors[f"attempt_{attempt}"] = str(e)
                        self.retry_setup(attempt, max_retries, logger, "Timeout")
                        continue

                    except requests.exceptions.RequestException as e:
                        raise Exception(f"Network error (no retry): {e}")

                    if response.status_code == 200:
                        break

                    if response.status_code == 413:
                        errors[f"attempt_{attempt}"] = f"Error {response.status_code} - {response.text}"
                        self.retry_setup(attempt, max_retries, logger, "413")
                        continue

                    exception_text = f"{response.status_code} - {response.text}"
                    errors[f"attempt_{attempt+1}"] = exception_text
                    raise Exception(exception_text)

                else:
                    raise Exception(f"Max retries exceeded. Errors appended:", json.dumps(errors, indent=2))

                results.append(response.json())

        return results

    def check_new_data(self, raw_data: dict) -> bool:
        # return bool(raw_data and raw_data.get(dataset_type))
        return not raw_data.empty

class NoOpLogger:
    def info(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass