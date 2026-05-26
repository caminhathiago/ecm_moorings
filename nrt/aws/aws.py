import os
from datetime import datetime

import pandas as pd
import glob
import boto3
from botocore.exceptions import ClientError

class CWBAWSS3:

    def __init__(self, aws_access_key_id:str, aws_secret_access_key:str, region_name:str, bucket:str, prefix:str):

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )

        self._bucket = bucket
        self._prefix = prefix


    def get_region(self, site) -> str:

        if site['archive_path']:
            return os.path.basename(site['archive_path']).replace("waves", "")
        else:
            raise ValueError(f"Unable to extract region as archive_path was not provided in buoys_metadata.csv")
        
    def compute_date_range(self, start_datetime:datetime, end_datetime:datetime) -> pd.DatetimeIndex:

        return pd.date_range(start_datetime, end_datetime)
    
    def compose_prefix(self, region:str, site_name:str, date:datetime) -> str:

        year = date.year 
        month = date.month if date.month >= 10 else f"0{date.month}" 
        day = date.day if date.day >= 10 else f"0{date.day}" 
        file_name = f"{site_name}_{year}{month}{day}.csv"

        return os.path.join(
                    # self._bucket,
                    self._prefix,
                    f"{region}waves", 
                    site_name, 
                    "text_archive", 
                    f"{year}",
                    f"{month}",
                    file_name
                ).replace("\\", "/")


    # def list_csvs(self, date:datetime, site_name:str) -> None:

    #     prefix = os.path.join()

    #     response = self.s3.list_objects_v2(Bucket=self._bucket, Prefix=self._prefix)

    
    def generate_needed_files_s3keys(self, site:pd.Series, start_datetime:datetime, end_datetime:datetime) -> list:

        region = self.get_region(site)
        date_range = self.compute_date_range(start_datetime, end_datetime)

        needed_files_keys = []
        for date in date_range:
            
            needed_files_keys.append(
                self.compose_prefix(region, site['name'], date)
            )

        return needed_files_keys

    def get_csvs(self, keys:list[str]) -> None:

        if isinstance(keys, str):
            keys = [keys]

        missing_data_errors = []

        dfs = []
        for key in keys:
            # dfs.append(
            #     pd.read_csv(f"s3://{key}")
            # )
            try:
                response = self.s3.get_object(Bucket=self._bucket, Key=key)

            except ClientError as e:
                error_code = e.response["Error"]["Code"]

                if error_code == "NoSuchKey":
                    missing_data_errors.append({"s3Key":key, "error":str(e)})
                    continue

                if error_code == "AccessDenied":
                    raise e
            
            dfs.append(
                pd.read_csv(response['Body'])
            )

        if not dfs:
            dfs = None
        else:
            dfs = pd.concat(dfs)

        return missing_data_errors, dfs

    def generate_daily_csv_keys(self, data_daily:list[dict], site:str) -> list[dict]:

        region = self.get_region(site)

        for day in data_daily:
            day['s3Key'] = self.compose_prefix(region, site['name'], day['date'])

        return data_daily

    def put_daily_csvs(self, day:dict) -> None:

        from io import StringIO

        csv_buffer = StringIO()
        day['data'].to_csv(csv_buffer, index=False)

        self.s3.put_object(
            Bucket=self._bucket,
            Key=day['s3Key'],
            Body=csv_buffer.getvalue()
        )
