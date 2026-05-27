from datetime import datetime, timedelta, UTC

from dotenv import load_dotenv
import pandas as pd
import numpy as np 

class ProcessEagleIOData:
    
    NO_DATA_CODES = {
        "period":1,
        "transmission":2,
        "latest_time":3
    }

    COLS_MAPPING = {
        'time_unix': ('Time (UNIX/UTC)', True),
        'timestamp': ('Timestamp (UTC)', False),
        'site': ('Site', False),
        'buoy_id': ('BuoyID', False),

        # Water Quality
        'WQ - WQ(1)- Temperature': ('SST (degC)', False),
        'TEMP_quality_control_sst': ('QF_sst', False),
        "WQ - WQ(3) Salinity PSU": ('Salinity (PSU)', False),

        # Winds
        'Weather - WindSpeedAvg': ('WindSpeed (m/s)', False),
        'Weather - WindDirection': ('WindDirec (deg)', False),

        # DSC currents:
        "DCS - Abs-Speed": ('CurrmentMag (m/s)', False),
        "DCS - Direction": ('CurrentDir (deg)', False),

        # Coords
        'Latitude': ('Latitude (deg)', False),
        'Longitude': ('Longitude (deg)', False),
    }

    COLS_ORDER = (
        'Time (UNIX/UTC)', 'Timestamp (UTC)', 'Site', 'BuoyID',
        'Hsig (m)', 'Hsig_swell (m)', 'Hsig_sea (m)',
        'Tp (s)', 'Tm (s)', 'Tm_swell (s)', 'Tm_sea (s)',
        'Dp (deg)', 'DpSpr (deg)', 'Dm (deg)',
        'Dm_swell (deg)', 'Dm_sea (deg)',
        'DmSpr (deg)', 'DmSpr_swell (deg)', 'DmSpr_sea (deg)',
        'QF_waves',
        'SST (degC)', 'QF_sst',
        'Bottom Temp (degC)', 'QF_bott_temp',
        'WindSpeed (m/s)', 'WindDirec (deg)',
        'CurrmentMag (m/s)','CurrentDir (deg)',
        'Latitude (deg)', 'Longitude (deg)',
        'Salinity (PSU)'
    )

    
    UNIT_CONVERSIONS = {
        ("cm/s", "m/s"): lambda x: x / 100,
        ("m/s", "cm/s"): lambda x: x * 100,
        ("degC", "K"): lambda x: x + 273.15,
        ("K", "degC"): lambda x: x - 273.15,
        ("knots", "m/s"): lambda x: x * 0.514444,
        ("m/s", "knots"): lambda x: x / 0.514444,
    }

    @staticmethod
    def get_time_col_name(data: pd.DataFrame) -> str:

        candidates = [
            col for col in data.columns
            if "timestamp" in col.lower() or col.lower() == "ts"
        ]

        if not candidates:
            raise ValueError("No time column found (expected 'timestamp' or 'ts')")

        return candidates[0]

    # @staticmethod
    # def response_to_dataframe(response_json: dict, parameters_payload: dict) -> pd.DataFrame:
        
    #     if response_json is None or not response_json.get("data"):
    #         return

    #     df = (
    #     pd.json_normalize(response_json["data"])
    #     .rename(columns=lambda c: c.replace("f.", "").replace(".v", ""))
    #     )

    #     col_map = ProcessEagleIOData.map_columns(parameters_payload)

    #     df = df.rename(columns=col_map)

    #     if "ts" in df.columns:
    #         df["ts"] = pd.to_datetime(df["ts"])

    #     return df
    
    @staticmethod
    def response_to_dataframe(response_json: dict) -> pd.DataFrame:

        if not response_json or not response_json.get("data"):
            return pd.DataFrame()

        header_cols = response_json.get("header", {}).get("columns", {})

        index_to_name = {
            str(idx): meta["name"]
            for idx, meta in header_cols.items()
        }

        df = pd.json_normalize(response_json["data"])

        df = df.rename(columns=lambda c: c.replace("f.", "").replace(".v", ""))

        df = df.rename(columns=index_to_name)

        if "ts" in df.columns:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)

        return df

    @staticmethod
    def map_columns(parameters_payload: dict) -> dict:
        return dict(
            zip(
                map(str, parameters_payload["cols_enum"]),
                parameters_payload["names"]
            )
        )

    @staticmethod
    def split_dailyly(df: pd.DataFrame, date_col: str="ts") -> dict[str, pd.DataFrame]:
        df[date_col] = pd.to_datetime(df[date_col])
        df["date"] = df[date_col].dt.date
        return {str(date): group.drop(columns=["date"]) for date, group in df.groupby("date")}

    @staticmethod
    def check_previous_new_data(previous_data:pd.DataFrame, new_raw_data: pd.DataFrame) -> bool:

        if previous_data is None or previous_data.empty:
            return new_raw_data is not None and not new_raw_data.empty       
        
        previous_time_col = ProcessEagleIOData.get_time_col_name(previous_data)
        latest_previous_time = pd.to_datetime(previous_data[previous_time_col], utc=True).max()

        new_raw_time_col = ProcessEagleIOData.get_time_col_name(new_raw_data)
        latest_new_time = pd.to_datetime(new_raw_data[new_raw_time_col]).max()

        if latest_previous_time >= latest_new_time:
            return False
        
        return True

    @staticmethod
    def convert_to_datetime(df: pd.DataFrame, old_col:str="ts", new_col:str="timestamp", drop_old:bool=False) -> pd.DataFrame:
        
        df[new_col] = pd.to_datetime(df[old_col], utc=True)
        df = df.sort_values(new_col)

        if drop_old:
            return df.drop(columns=old_col)
        
        return df

    @staticmethod
    def process_time_unix_column(data:pd.DataFrame, method:str='create') -> pd.DataFrame:
        
        time_col = ProcessEagleIOData.get_time_col_name(data)

        time_unix_col = 'time_unix'
        
        if method == 'create':
            data[time_unix_col] = data[time_col].astype("int64") // 10**6

        elif method == 'drop':
            reverse_map = {
                v[0]: k
                for k, v in ProcessEagleIOData.COLS_MAPPING.items()
                if "unix" in v[0].lower()
            }
            data = data.rename(columns=reverse_map)
            data = data.drop(columns=time_unix_col)

        return data  

    @staticmethod
    def conform_cols_to_auswaves(data: pd.DataFrame, strip: bool=True) -> pd.DataFrame:
        
        mapping = {}

        for k, (name, to_strip) in ProcessEagleIOData.COLS_MAPPING.items():
            if not strip and not to_strip:
                mapping[name] = f" {name}"
            else:
                mapping[k] = name

        return data.rename(columns=mapping)

    @staticmethod
    def create_missing_columns(data:pd.DataFrame) -> pd.DataFrame:

        missing_cols = [col for col in ProcessEagleIOData.COLS_ORDER if col not in data.columns]

        if not missing_cols:
            return data
        
        for col in missing_cols:
            if "QF" in col:
                data[col] = 2
            else:
                data[col] = np.nan

        return data

    @staticmethod
    def drop_unwanted_columns(data:pd.DataFrame) -> pd.DataFrame:
        
        cols_to_drop = [
            col for col in data.columns
            if col not in ProcessEagleIOData.COLS_ORDER
        ]
        
        return data.drop(columns=cols_to_drop)

    @staticmethod
    def fill_nan_9999(data:pd.DataFrame) -> pd.DataFrame:
        return data.fillna(-9999.0)
    
    @staticmethod
    def reorder_cols(data:pd.DataFrame) -> pd.DataFrame:
        
        columns_new_order = [col for col in ProcessEagleIOData.COLS_ORDER if col in data.columns]
        return data[columns_new_order]

    @staticmethod
    def interpolate_latlon(data:pd.DataFrame) -> pd.DataFrame:
        
        if 'Latitude' in data.columns and 'Longitude' in data.columns:
            
            data['Latitude'] = (
                data['Latitude']
                .interpolate(method='nearest', limit_direction='both')
                .bfill()
                .ffill()
            )
            
            data['Longitude'] = (
                data['Longitude']
                .interpolate(method='nearest', limit_direction='both')
                .bfill()
                .ffill()
            )
        
        return data

    @staticmethod
    def concat_previous_new(previous_data:pd.DataFrame,
                            new_data:pd.DataFrame,
                            overwrite:bool=False,
                            add_new_variable:bool=False,
                            raw_data:bool=False) -> pd.DataFrame:

        if previous_data is None:
            return new_data

        if not add_new_variable and not raw_data:
            if not previous_data.columns.equals(new_data.columns):
                raise KeyError(f"Mismatch of columns between new_data and previous data. new_data columns: {new_data.columns}; previous_data columns:{previous_data.columns}")

        if not overwrite:
        
            time_col = ProcessEagleIOData.get_time_col_name(previous_data)            

            latest_processed_time = previous_data[time_col].max()

            new_data = new_data[new_data[time_col] > latest_processed_time]

        concat_data = pd.concat([previous_data, new_data], ignore_index=True)
        
        return concat_data

    @staticmethod
    def drop_timestamp_duplicates(data:pd.DataFrame, time_col:str="Timestamp (UTC)") -> pd.DataFrame:
        return data.drop_duplicates(subset=time_col)

    @staticmethod
    def extract_dates_from_dataframe(data:pd.DataFrame, time_col=" Timestamp (UTC)") -> list[datetime]:
        return data[time_col].dt.date.unique()

    @staticmethod
    def split_data_daily(data:pd.DataFrame) -> pd.DataFrame:

        time_col = ProcessEagleIOData.get_time_col_name(data)

        dates = ProcessEagleIOData.extract_dates_from_dataframe(data, time_col)

        dfs = []
        for date in dates:
            df = (data
                  .set_index(time_col)
                  .loc[str(date)]
                  .reset_index()
            )

            # swap order between timestamp and timeunix columns
            cols = df.columns.tolist()
            cols[0], cols[1] = cols[1], cols[0]
            df = df[cols]

            dfs.append({"date":date, "data":df})

        return dfs

    @staticmethod
    def strip_columns(data:pd.DataFrame) -> pd.DataFrame:

        stripped_cols = data.columns.str.strip()
        data.columns = stripped_cols

        return data

    @staticmethod
    def conform_timestamp_format_auswaves(dfs:list[pd.DataFrame], time_col=" Timestamp (UTC)") -> list[pd.DataFrame]:

        for date in dfs:
            data = date['data']
            # time_col = ProcessEagleIOData.get_time_col_name(data)
            data[time_col] = pd.to_datetime(data[time_col]).dt.strftime("%d-%b-%Y %H:%M:%S")
            date['data'] = data

        return dfs
    
    @staticmethod
    def convert_units(data:pd.DataFrame, ecm_parameters:pd.DataFrame) -> pd.DataFrame:
        
        params_to_convert = ecm_parameters.dropna(subset='convert_unit_to')

        for _, param in params_to_convert.iterrows():

            param_name = param["name"]
            from_unit = param["unit"]
            to_unit = param["convert_unit_to"]

            if from_unit == to_unit:
                continue

            func = ProcessEagleIOData.UNIT_CONVERSIONS.get((from_unit, to_unit))

            if func is None:
                raise ValueError(
                    f"No conversion rule for {from_unit} -> {to_unit}"
                )

            data[param_name] = func(data[param_name])

        return data
    
    @staticmethod
    def correct_true_north(data:pd.DataFrame, latitude:float, longitude:float) -> pd.DataFrame:
        
        dir_cols = [col for col in data.columns if "direct" in col.lower()]

        if not dir_cols:
            return data

        decimal_year = (
            datetime.now(UTC).year
            + (datetime.now(UTC).timetuple().tm_yday - 1) / 365.25
        )

        from pygeomag import GeoMag
        gm = GeoMag()

        mag_dec = gm.calculate(
                glat=latitude,
                glon=longitude,
                alt=0, # sea level in km
                time=decimal_year
                ).dec
        mag_dec = round(mag_dec, 2)

        for col in dir_cols:
            data[col] = (data[col] + mag_dec) % 360

        return data
