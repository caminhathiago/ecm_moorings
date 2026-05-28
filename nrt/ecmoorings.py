import os
from datetime import datetime

from importlib.resources import files
import numpy as np
import pandas as pd

class ECMoorings:

    def load_ecm_sites(self) -> pd.DataFrame:        
        return pd.read_csv(files("nrt.config").joinpath("ecm_sites.csv"))

    def load_ecm_parameters(self) -> pd.DataFrame:
        return pd.read_csv(files("nrt.config").joinpath("ecm_parameters.csv"))

    def load_buoys_metadata(self) -> pd.DataFrame: 
        df = pd.read_csv(os.getenv("BUOYS_METADATA_PATH"))
        return df[df['type']=='ecm']

    def create_parameters_payload(self, parameters_sel: pd.DataFrame) -> dict:
        return {
            "ids": parameters_sel['eagle_parameter_id'].tolist(),
            "names": parameters_sel['name'].tolist(),
            "cols_enum": np.arange(len(parameters_sel))
        }
    
    def get_region(self, site) -> str:

        if site['archive_path']:
            return os.path.basename(site['archive_path']).replace("waves", "")
        else:
            raise ValueError(f"Unable to extract region as archive_path was not provided in buoys_metadata.csv")

    def generate_daily_csv_paths(self, 
                                 data_daily:list[dict], 
                                 site:str,
                                 incoming_path:str, 
                                 enable_region_folder_structure:bool=False, 
                                 data_folder:str="text_archive") -> list[dict]:

        if enable_region_folder_structure:
            region = self.get_region(site)
        else:
            region = None

        for day in data_daily:
            day['local_path'] = self.compose_path(incoming_path, region, site['name'], day['date'], data_folder=data_folder)

        return data_daily

    def compose_path(self, 
                     incoming_path:str, 
                     region:str | None, 
                     site_name:str, 
                     date:datetime, 
                     data_folder:str="text_archive") -> str:

        if region:
            path_parts.append(f"{region}waves")

        if data_folder not in ("raw_data", "text_archive"):
            raise ValueError(f"Invalid data_folder: {data_folder}. Must be 'raw_data' or 'text_archive'.")
        
        year = date.year
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        file_name = f"{site_name}_{year}{month}{day}.csv"

        path_parts = [
            incoming_path,
        ]

        path_parts.extend([
            "sites",
            site_name,
            data_folder,
            str(year),
            month,
            file_name
        ])

        return os.path.join(*path_parts)#.replace("\\", "/")
    
    def save_daily_csvs(self, day:dict) -> None:

        parent_folder = os.path.dirname(day['local_path'])
        os.makedirs(parent_folder, exist_ok=True)

        day['data'].to_csv(day['local_path'], index=False)