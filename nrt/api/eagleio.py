import os
import json
from datetime import datetime, timedelta, UTC

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

    def fetch_historic_data(
        self,
        params_ids: list[str],
        start_datetime: datetime=datetime.now(UTC)-timedelta(hours=24),
        end_datetime: datetime=datetime.now(UTC),
    ):

        headers = {
            "X-API-Key": self.api_key
        }

        endpoint = "historic/"
        
        args = {
            "startTime": start_datetime.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "endTime": end_datetime.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "params": ",".join(params_ids)
        }

        response = requests.get(self.base_url + endpoint, headers=headers, params=args)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error: {response.status_code} - {response.text}")

    def check_new_data(self, raw_data: dict, dataset_type: str = "data") -> bool:
        return bool(raw_data and raw_data.get(dataset_type))