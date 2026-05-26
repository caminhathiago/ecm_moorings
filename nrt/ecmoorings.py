
import os

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

    def load_previous_data():
        pass