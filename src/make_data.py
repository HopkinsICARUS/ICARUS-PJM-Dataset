#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 15 11:30:41 2025

@author: Originally created by Christoph Graf, modified by Saroj Khanal
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional


def make_load_data(path2file: Path, sheet_name: str, region_prefix: Optional[str] = None) -> pd.DataFrame:
    """Loads and reshapes load curve data, optionally filtering for a specific region prefix."""
    # Load Duration Curves are in Pacific Time
    dt = pd.read_excel(path2file, sheet_name=sheet_name, skiprows=3, skipfooter=2)
    if "Unnamed: 0" in dt.columns:
        dt.drop("Unnamed: 0", axis=1, inplace=True)

    # Pre-filter by region prefix if provided to simplify processing # Unliked Other files where "Region Name" is used, here it's just "Region"
    if region_prefix and "Region" in dt.columns:
        dt = dt[dt["Region"].str.startswith(region_prefix, na=False)].copy()

    regions = np.unique(dt["Region"])
    if len(regions) == 0:
        return pd.DataFrame() # Return empty if no regions match

    out = pd.DataFrame(columns=["Month", "Day", "Hour"] + list(regions))
    out["Month"] = np.repeat(dt.loc[dt["Region"] == regions[0], "Month"].values, 24)
    out["Day"] = np.repeat(dt.loc[dt["Region"] == regions[0], "Day"].values, 24)
    out["Hour"] = np.tile(np.arange(1, 25), 365)
    out = out.reset_index().rename({"index": "Time"}, axis=1)
    for region in regions:
        for h in range(1, 25):
            out.loc[out.Hour == h, region] = dt.loc[
                dt.Region == region, "Hour " + str(h)
            ].values

    return out


def make_transport_limit_data(path2file: Path, sheet_name: str, snapshot_year: int) -> pd.DataFrame:
    """Loads and cleans transmission capacity data."""
    dt = pd.read_excel(path2file, sheet_name=sheet_name, skiprows=3, skipfooter=2)
    if "Unnamed: 0" in dt.columns:
        dt.drop("Unnamed: 0", axis=1, inplace=True)

    dt = dt[["From", "To", snapshot_year]]
    var_name = f"TTC_Capacity_{snapshot_year}"
    dt.rename({snapshot_year: var_name}, axis=1, inplace=True)

    dt = dt.loc[~((dt.From.isna()) & (dt.To.isna()))].copy()
    dt[var_name] = pd.to_numeric(dt[var_name], errors="coerce")

    dt["From"] = dt["From"].ffill()

    dt = dt.dropna(subset=["From", "To", var_name])
    dt = dt.loc[dt[var_name] > 0]

    dt = dt.reset_index(drop=True)
    dt["Line"] = dt.From.astype(str) + "-" + dt.To.astype(str)
    dt = dt[["Line", "From", "To", var_name]]

    return dt


def make_generator_data(path2file: Path, sheet_name: str, region_prefix: Optional[str] = None) -> pd.DataFrame:
    """Loads generator data, optionally filtering for a specific region prefix."""
    dt = pd.read_excel(path2file, sheet_name=sheet_name)

    # Filter by region prefix if provided and a 'Region' column exists
    if region_prefix and "Region Name" in dt.columns:
        dt = dt[dt["Region Name"].str.startswith(region_prefix, na=False)].copy()

    return dt


def make_res_data(path2file: Path, sheet_name: str, res: str, region_prefix: Optional[str] = None) -> pd.DataFrame:
    """Loads and reshapes renewable generation profiles, optionally filtering for a region prefix."""
    dt = pd.read_excel(path2file, sheet_name=sheet_name, skiprows=3)
    if "Unnamed: 0" in dt.columns:
        dt.drop("Unnamed: 0", axis=1, inplace=True)

    # Pre-filter by region prefix if provided
    if region_prefix and "Region Name" in dt.columns:
        dt = dt[dt["Region Name"].str.startswith(region_prefix, na=False)].copy()

    id_vars = [col for col in dt.columns if not col.startswith("Hour")]
    value_vars = [col for col in dt.columns if col.startswith("Hour")]

    if not value_vars or dt.empty:
        return pd.DataFrame()

    out = pd.melt(
        dt,
        id_vars=id_vars,
        value_vars=value_vars,
        var_name="Hour",
        value_name="kWh of Generation per MW of Capacity",
    )
    out["Hour"] = out["Hour"].str.extract(r'(\d+)').astype(int)
    sort_columns = [col for col in id_vars if col in out.columns] + ["Hour"]
    out = out.sort_values(by=sort_columns).reset_index(drop=True)

    return out


def write_transport_splits(dt_transport_cap: pd.DataFrame, outdir: Path, prefix: str):
    """
    Splits transport capacity data based on a region prefix and saves them to a dedicated subfolder.
    """
    # The prefix now defines a subfolder for the output files
    output_dir = outdir / prefix
    output_dir.mkdir(parents=True, exist_ok=True)

    def _starts_with_prefix(x: object, p: str) -> bool:
        return pd.notna(x) and str(x).strip().startswith(p)

    is_from = dt_transport_cap["From"].apply(lambda x: _starts_with_prefix(x, prefix))
    is_to = dt_transport_cap["To"].apply(lambda x: _starts_with_prefix(x, prefix))

    # 1) Internal lines
    lines = dt_transport_cap[is_from & is_to].copy()
    lines.to_csv(output_dir / "lines.csv", index=False)

    # 2) Imports => generators_interface
    generators_interface = dt_transport_cap[~is_from & is_to].copy()
    generators_interface.to_csv(output_dir / "generators_interface.csv", index=False)

    # 3) Exports => load_interface
    load_interface = dt_transport_cap[is_from & ~is_to].copy()
    load_interface.to_csv(output_dir / "load_interface.csv", index=False)
    
    print(f"Successfully split transport capacity data into '{output_dir}'.")


def get_output_path(directory: Path, base_name: str, prefix: Optional[str]) -> Path:
    """Constructs a CSV filepath, creating a subdirectory if a prefix is provided."""
    output_dir = directory
    if prefix:
        output_dir = directory / prefix
    
    # Ensure the target directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return output_dir / f"{base_name}.csv"


def main():
    """Main script to process and save EPA Zonal Model data."""
    # --- CONFIGURATION ---
    # Set a prefix to filter for a specific region (e.g., "PJM").
    # Set to "", which is None, to process all regions.
    REGION_PREFIX = "PJM"

    # --- SETUP ---
    data_dir = Path(Path.cwd(), "data")
    raw_dir = Path(Path.cwd(), "rawdata/epa-2023-reference-case")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Processing data. Active region filter: {REGION_PREFIX or 'None'}")
    if REGION_PREFIX:
        print(f"Filtered output will be saved in: {data_dir / REGION_PREFIX}")

    # --- PROCESSING ---
    dt_load = make_load_data(
        path2file=raw_dir / "table-2-2-load-curves-used-in-epa-2023-reference-case.xlsx",
        sheet_name="Table 2-2",
        region_prefix=REGION_PREFIX,
    )
    dt_load.to_csv(get_output_path(data_dir, "load", REGION_PREFIX), index=False)

    dt_transport_cap = make_transport_limit_data(
        path2file=raw_dir / "table-3-27-annual-transmission-capabilities-of-u.s.-model-regions-in-epa-2023-reference-case.xlsx",
        sheet_name="Table 3-27",
        snapshot_year=2028,
    )
    # Always save the full, unfiltered transport capacity data
    dt_transport_cap.to_csv(data_dir / "transport_cap_all.csv", index=False)
    if REGION_PREFIX:
        write_transport_splits(dt_transport_cap, data_dir, prefix=REGION_PREFIX)

    # Process generator data
    dt_generators = make_generator_data(
        path2file=raw_dir / "needs-rev-06-06-2024.xlsx",
        sheet_name="NEEDS_Active",
        region_prefix=REGION_PREFIX,
    )
    dt_generators.to_csv(get_output_path(data_dir, "generators", REGION_PREFIX), index=False)
    
    dt_retirements = make_generator_data(
        path2file=raw_dir / "needs-rev-06-06-2024.xlsx",
        sheet_name="NEEDS_retireby2028",
        region_prefix=REGION_PREFIX,
    )
    dt_retirements.to_csv(get_output_path(data_dir, "generator_retirements_by_2028", REGION_PREFIX), index=False)

    # Process renewable energy data
    res_files = {
        "wind_onshore": ("table-4-37-wind-generation-profiles-in-epa-2023-reference-case-kwh-of-generation-per-mw-of-capacity.xlsx", "Onshore", "Wind"),
        "wind_offshore_fixed": ("table-4-37-wind-generation-profiles-in-epa-2023-reference-case-kwh-of-generation-per-mw-of-capacity.xlsx", "Offshore Fixed", "Wind"),
        "wind_offshore_floating": ("table-4-37-wind-generation-profiles-in-epa-2023-reference-case-kwh-of-generation-per-mw-of-capacity.xlsx", "Offshore Floating", "Wind"),
        "solar": ("table-4-41-solar-photovoltaic-generation-profiles-in-epa-2023-reference-case-kwh-of-generation-per-mw-of-capacity.xlsx", "Table 4-41", "Solar"),
    }

    for name, (file, sheet, res_type) in res_files.items():
        dt_res = make_res_data(
            path2file=raw_dir / file,
            sheet_name=sheet,
            res=res_type,
            region_prefix=REGION_PREFIX,
        )
        dt_res.to_csv(get_output_path(data_dir, name, REGION_PREFIX), index=False)

    print("\nProcessing complete.")


if __name__ == "__main__":
    main()