"""
Real-time QC tests following the IOOS QARTOD manual for In-situ Temperature
and Salinity (Update 2, March 2020):
https://cdn.ioos.noaa.gov/media/2020/03/QARTOD_TS_Manual_Update2_200324_final.pdf
"""
import numpy as np
import pandas as pd


class QARTODFlags:
    PASS = 1
    NOT_EVALUATED = 2
    SUSPECT = 3
    FAIL = 4
    MISSING = 9


# Test 8 (Flat Line) thresholds, keyed by AusWaves column name.
# The manual leaves the thresholds to the operator; its examples are
# REP_CNT_FAIL = 5, REP_CNT_SUSPECT = 3, EPS = 0.05. Those examples flag
# 38-72% of good ECM data (15-min sampling, Exmouth Gulf), so the values
# below are tuned locally:
#   - EPS is half the sensor's reporting step, so only exact repeats count
#     (a full step fails due to float round-off: |22.594 - 22.595| < 0.001).
#   - REP_CNTs are counts of previous observations; at 15-min sampling
#     4/8 = suspect after 1 h / fail after 2 h of identical values.
FLAT_LINE_CONFIG = {
    "SST (degC)": {
        "flag_col": "QF_sst",
        "suspect_threshold": 4,  # REP_CNT_SUSPECT
        "fail_threshold": 8,     # REP_CNT_FAIL
        "tolerance": 0.0005,     # EPS (SST reported to 0.001 degC)
    },
    # Salinity is reported to 0.01 PSU and naturally repeats for up to ~6 h
    # (24 obs), so it needs much longer counts. Not enabled because the
    # AusWaves CSV has no salinity flag column.
    # "Salinity (PSU)": {
    #     "flag_col": "QF_salinity",
    #     "suspect_threshold": 12,
    #     "fail_threshold": 24,
    #     "tolerance": 0.005,
    # },
}


def flat_line_test(values: pd.Series,
                   suspect_threshold: int = 3,
                   fail_threshold: int = 5,
                   tolerance: float = 0.05) -> pd.Series:
    """
    QARTOD Test 8 - Flat Line Test.

    Observation n is compared to the previous REP_CNT observations. If
    |x_n - x_(n-i)| < EPS for every i in 1..REP_CNT_FAIL, x_n is flagged FAIL;
    otherwise, if that holds for every i in 1..REP_CNT_SUSPECT, x_n is flagged
    SUSPECT; otherwise PASS.

    Missing values (NaN) are flagged MISSING and skipped, so "previous
    observations" are the previous valid ones. Observations without enough
    history pass, as in the manual's codable instructions.

    `values` must be sorted in time.
    """
    if not 0 < suspect_threshold < fail_threshold:
        raise ValueError("Flat line thresholds must satisfy 0 < suspect_threshold < fail_threshold.")

    # work positionally so duplicated/unsorted index labels don't matter
    x = pd.to_numeric(values, errors="coerce").to_numpy(dtype="float64")
    flags = np.full(x.shape, QARTODFlags.MISSING, dtype="int64")

    is_valid = ~np.isnan(x)
    valid = x[is_valid]

    if valid.size:
        # within_eps[:, i-1] is True when |x_n - x_(n-i)| < EPS
        within_eps = np.zeros((valid.size, fail_threshold), dtype=bool)
        for i in range(1, fail_threshold + 1):
            within_eps[i:, i - 1] = np.abs(valid[i:] - valid[:-i]) < tolerance

        is_suspect = within_eps[:, :suspect_threshold].all(axis=1)
        is_fail = within_eps.all(axis=1)

        flags[is_valid] = np.select([is_fail, is_suspect],
                                    [QARTODFlags.FAIL, QARTODFlags.SUSPECT],
                                    default=QARTODFlags.PASS)

    return pd.Series(flags, index=values.index, name=values.name)


def apply_flat_line_tests(data: pd.DataFrame, config: dict = FLAT_LINE_CONFIG, logger=None) -> pd.DataFrame:
    """Run the flat line test on each configured column present in `data` and
    write the flags to that column's flag column. Columns not in `data` are
    skipped."""
    for col, params in config.items():

        if col not in data.columns:
            if logger:
                logger.info(f"Flat line test skipped for {col}: column not found")
            continue

        data[params["flag_col"]] = flat_line_test(
            data[col],
            suspect_threshold=params["suspect_threshold"],
            fail_threshold=params["fail_threshold"],
            tolerance=params["tolerance"],
        )

        if logger:
            counts = data[params["flag_col"]].value_counts().sort_index().to_dict()
            logger.info(f"Flat line test on {col} -> {params['flag_col']} flag counts: {counts}")

    return data
