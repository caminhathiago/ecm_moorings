from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime, UTC

import numpy as np
import pandas as pd

@dataclass
class AlertEvent:
    alert_type: str
    triggered: bool
    title: str
    message: str
    site_name: pd.Series | None = None
    # default_factory: evaluated per event, not once at import time
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict | None = None


class Alert(ABC):

    def __init__(self, severity="warning"):
        self.severity = severity
        self.alert_type = self.__class__.__name__.lower().replace(" ", "_")

    @abstractmethod
    def evaluate(self, buoy):
        pass

    def get_time_col(self, data: pd.DataFrame) -> str | None:
        # exact names first: substring matching ("time"/"ts") also hits
        # parameters such as "Ai1 - ProcessingTime" or "... Gusts"
        for col in data.columns:
            if col.strip().lower() in ("ts", "timestamp", "timestamp (utc)"):
                return col

        for col in data.columns:
            if "timestamp" in col.lower():
                return col

        return None

    def sort_by_time(self, data: pd.DataFrame) -> tuple[pd.DataFrame, str]:
        time_col = self.get_time_col(data)
        if time_col is None:
            raise ValueError(f"No timestamp column found for {self.alert_type} evaluation.")

        data = data.copy()
        data[time_col] = pd.to_datetime(data[time_col], utc=True, errors="coerce")

        if data[time_col].isna().any():
            raise ValueError(f"Invalid timestamps found in data for {self.alert_type} evaluation.")

        return data.sort_values(time_col), time_col


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
            if "latitude" in col.lower():
                lat_col = col
            elif "longitude" in col.lower():
                lon_col = col

        return lat_col, lon_col

    def calculate_distance(self, lats, lons, lat_center, lon_center):

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

    def calculate_velocity(self, lats: pd.Series, lons: pd.Series, timestamps: pd.Series):
        # drift speed between consecutive GPS fixes
        step_m = self.calculate_distance(lats, lons, lats.shift(), lons.shift())
        time_diff = timestamps.diff().dt.total_seconds()

        velocity_ms = step_m / time_diff
        velocity_kt = velocity_ms * 1.94384

        return velocity_ms, velocity_kt

    def evaluate(self, data:pd.DataFrame):

        lat_col, lon_col = self.get_latlon_cols(data)
        if lat_col is None or lon_col is None:
            raise ValueError("No latitude/longitude columns found for geofence evaluation.")

        data, time_col = self.sort_by_time(data)
        data = data.dropna(subset=[lat_col, lon_col])

        if data.empty:
            return AlertEvent(
                triggered=False,
                site_name=self.site_name,
                alert_type="geofence_alert",
                title=f"{self.site_name} has no GPS fixes",
                message="No latitude/longitude values in the evaluated window.",
            )

        distances_m = self.calculate_distance(
            data[lat_col],
            data[lon_col],
            self.lat,
            self.lon
        )

        velocity_ms, velocity_kt = self.calculate_velocity(data[lat_col], data[lon_col], data[time_col])

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

    def evaluate(self, data:pd.DataFrame):

        data, time_col = self.sort_by_time(data)

        latest_time = (datetime.now(UTC) - data[time_col].max()).total_seconds() / 3600

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

        data, _ = self.sort_by_time(data)

        # rows from other sensors have no voltage; use the latest actual reading
        voltages = pd.to_numeric(data[voltage_col], errors="coerce").dropna()

        if voltages.empty:
            return AlertEvent(
                triggered=False,
                site_name=self.site_name,
                alert_type="battery_voltage_alert",
                title=f"{self.site_name} has no battery voltage readings",
                message="No battery voltage values in the evaluated window.",
            )

        latest_voltage = voltages.iloc[-1]

        triggered = latest_voltage < self.min_voltage

        return AlertEvent(
            triggered=triggered,
            site_name=self.site_name,
            alert_type="battery_voltage_alert",
            title=f"{self.site_name} buoy battery < {self.min_voltage} V",
            message=f"Latest voltage reading is {latest_voltage:.2f} V (< {self.min_voltage} V).",
        )
