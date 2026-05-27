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
    
    def compose_prefix(self, region:str | None, site_name:str, date:datetime, data_folder:str="text_archive") -> str:

        year = date.year
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        file_name = f"{site_name}_{year}{month}{day}.csv"

        path_parts = [
            self._prefix,
        ]

        if region:
            path_parts.append(f"{region}waves")

        if data_folder not in ("raw_data", "text_archive"):
            raise ValueError(f"Invalid data_folder: {data_folder}. Must be 'raw_data' or 'text_archive'.")

        path_parts.extend([
            site_name,
            data_folder,
            str(year),
            month,
            file_name
        ])

        return os.path.join(*path_parts).replace("\\", "/")


    # def list_csvs(self, date:datetime, site_name:str) -> None:

    #     prefix = os.path.join()

    #     response = self.s3.list_objects_v2(Bucket=self._bucket, Prefix=self._prefix)

    
    def generate_needed_files_s3keys(self,
                                     site:pd.Series,
                                     start_datetime:datetime,
                                     end_datetime:datetime,
                                     enable_region_folder_structure:bool=False,
                                     data_folder:str="text_archive") -> list:

        if enable_region_folder_structure:
            region = self.get_region(site)
        else:
            region = None
        
        date_range = self.compute_date_range(start_datetime, end_datetime)

        needed_files_keys = []
        for date in date_range:
            
            needed_files_keys.append(
                self.compose_prefix(region, site['name'], date, data_folder)
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

    def generate_daily_csv_keys(self, data_daily:list[dict], site:str, enable_region_folder_structure:bool=False, data_folder:str="text_archive") -> list[dict]:

        if enable_region_folder_structure:
            region = self.get_region(site)
        else:
            region = None

        for day in data_daily:
            day['s3Key'] = self.compose_prefix(region, site['name'], day['date'], data_folder=data_folder)

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
