from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime, UTC

import pandas as pd

@dataclass
class AlertEvent:
    alert_type: str
    triggered: bool
    title: str
    message: str
    site_name: pd.Series | None = None
    timestamp: datetime = datetime.now(UTC)
    payload: dict | None = None


class Alert(ABC):

    def __init__(self, severity="warning"):
        self.severity = severity
        self.alert_type = self.__class__.__name__.lower().replace(" ", "_")

    @abstractmethod
    def evaluate(self, buoy):
        pass

    @abstractmethod
    def get_time_col(self, data):
        pass

class GeofenceAlert(Alert):

    def __init__(self, site_name:str, lat, lon, search_rad):
        super().__init__("Geofence")
        self.site_name = site_name
        self.lat = lat
        self.lon = lon
        self.search_rad = search_rad

    def get_latlon_cols(self, data:pd.DataFrame) -> tuple:
        lat_col = None
        lon_col = None

        for col in data.columns:
            if "lat" in col.lower():
                lat_col = col
            elif "lon" in col.lower():
                lon_col = col

        return lat_col, lon_col
    
    def get_time_col(self, data:pd.DataFrame) -> str:
        timestamp_col = None

        for col in data.columns:
            if "time" in col.lower() or "ts" in col.lower():
                timestamp_col = col
                break

        return timestamp_col

    def calculate_distance(self, lats, lons, lat_center, lon_center):

        import numpy as np
        lats_radians = np.radians(lats)
        lons_radians = np.radians(lons)
        lat_center_radians = np.radians(lat_center)
        lon_center_radians = np.radians(lon_center)

        dlat = lat_center_radians - lats_radians
        dlon = lon_center_radians - lons_radians

        R = 6371000
        a = np.sin(dlat/2)**2 + np.cos(lats_radians) * np.cos(lat_center_radians) * np.sin(dlon/2)**2
        distances = 2 * R * np.arcsin(np.sqrt(a))
        
        return distances

    def calculate_velocity(self, distances, timestamps):
        
        time_col = self.get_time_col(timestamps)
        if time_col is None:
            raise ValueError("No timestamp column found for velocity calculation.")
        
        timestamps = pd.to_datetime(timestamps[time_col])

        time_diff = timestamps.diff().dt.total_seconds()
        velocity_ms = distances / time_diff
        velocity_kt = velocity_ms * 1.94384

        return velocity_ms, velocity_kt


    def evaluate(self, data:pd.DataFrame):

        lat_col, lon_col = self.get_latlon_cols(data)
        data = data.dropna(subset=[lat_col, lon_col])

        distances_m = self.calculate_distance(
            data[lat_col],
            data[lon_col],
            self.lat,
            self.lon
        )

        velocity_ms, velocity_kt = self.calculate_velocity(distances_m, data)

        triggered = distances_m.iloc[-1] > self.search_rad

        return AlertEvent(
            triggered=triggered,
            site_name=self.site_name,
            alert_type="geofence_alert",
            title=f"{self.site_name} is out of radius",
            message=f"Buoy is {distances_m.iloc[-1]:.0f} m from target position drifting at {velocity_kt.iloc[-1]:.1f} kt.",
            payload={
                "distances_m": distances_m,
                "velocity_ms": velocity_ms,
                "velocity_kt": velocity_kt
            }   
        )

    
class TimefenceAlert(Alert):

    def __init__(self, site_name:str, max_gap_hours=int(24)):
        super().__init__("Timefence")
        self.site_name = site_name
        self.max_gap_hours = max_gap_hours

    def get_time_col(self, data:pd.DataFrame) -> str:
        timestamp_col = None

        for col in data.columns:
            if "time" in col.lower() or "ts" in col.lower():
                timestamp_col = col
                break

        return timestamp_col

    def evaluate(self, data:pd.DataFrame):
        
        time_col = self.get_time_col(data)
        if time_col is None:
            raise ValueError("No timestamp column found for timefence evaluation.")
        
        data[time_col] = pd.to_datetime(data[time_col], errors="coerce")

        if data[time_col].isna().any():
            raise ValueError("Invalid timestamps found in data for timefence evaluation.")

        time_gap_hours = (datetime.now(UTC) - data[time_col]).dt.total_seconds() / 3600

        latest_time = time_gap_hours.iloc[-1]

        triggered = latest_time > self.max_gap_hours
        
        return AlertEvent(
            triggered=triggered,
            site_name=self.site_name,
            alert_type="timefence_alert",
            title=f"{self.site_name} buoy data > {self.max_gap_hours} hrs old",
            message=f"Last data point is {latest_time:.1f} hours old.",
        )


class BatteryVoltageAlert(Alert):
    
    def __init__(self, site_name:str, min_voltage=float(11.0)):
        super().__init__("BatteryVoltage")
        self.site_name = site_name
        self.min_voltage = min_voltage

    def get_time_col(self, data:pd.DataFrame) -> str:
        timestamp_col = None

        for col in data.columns:
            if "time" in col.lower() or "ts" in col.lower():
                timestamp_col = col
                break

        return timestamp_col
    
    def get_voltage_col(self, data:pd.DataFrame) -> str:
        
        voltage_col = None
        for col in data.columns:
            if "batteryvoltage" in col.lower():
                voltage_col = col
                break

        return voltage_col

    def evaluate(self, data:pd.DataFrame):
        
        voltage_col = self.get_voltage_col(data)

        if voltage_col is None:
            raise ValueError("No BatteryVoltage column found for battery voltage evaluation.")

        latest_voltage = data[voltage_col].iloc[-1]

        triggered = latest_voltage < self.min_voltage

        return AlertEvent(
            triggered=triggered,
            site_name=self.site_name,
            alert_type="battery_voltage_alert",
            title=f"{self.site_name} buoy battery < {self.min_voltage} V",
            message=f"Latest voltage reading is {latest_voltage:.2f} V (< {self.min_voltage} V).",
        )