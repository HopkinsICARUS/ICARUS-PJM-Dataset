#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 29 12:22:15 2025

@author: Originally created by Christoph Graf, modified by Saroj Khanal
"""

import numpy as np
import geopandas as gpd
import pandas as pd
import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap
from matplotlib import cm
from pathlib import Path
from matplotlib import patheffects as pe
# --- MODIFICATION: Import Patch for creating the color legend ---
from matplotlib.patches import Patch

# --- CONFIGURATION ---
# Simply change this prefix to generate a map for a different region (e.g., "PJM", "NY")
REGION_PREFIX = "PJM"

def generate_colormap(N):
    """Generates a visually distinct colormap for N categories."""
    arr = np.arange(N) / N
    N_up = int(math.ceil(N / 7) * 7)
    arr.resize(N_up)
    arr = arr.reshape(7, N_up // 7).T.reshape(-1)
    ret = cm.hsv(arr)
    n = ret[:, 3].size
    a = n // 2
    b = n - a
    for i in range(3):
        ret[0 : n // 2, i] *= np.arange(0.2, 1, 0.8 / a)
    ret[n // 2 :, 3] *= np.arange(1, 0.1, -0.9 / b)
    return ret

# --- 1. LOAD GEOSPATIAL BASEMAP DATA ---
print("Loading geospatial data...")
us_states_path = Path(Path.cwd(), "rawdata", "epa-2023-reference-case", "cb_2018_us_state_500k.zip")
us_states = gpd.read_file(us_states_path)
states2drop_names = ["Alaska", "Hawaii", "Puerto Rico", "Commonwealth of the Northern Mariana Islands", "United States Virgin Islands", "American Samoa", "Guam"]
states2drop_fp = us_states.loc[us_states["NAME"].isin(states2drop_names), "STATEFP"].values
us_states = us_states.loc[~us_states["NAME"].isin(states2drop_names)]
us_counties_path = Path(Path.cwd(), "rawdata", "epa-2023-reference-case", "cb_2018_us_county_500k.zip")
us_counties = gpd.read_file(us_counties_path)
us_counties = us_counties.dropna()
us_counties = us_counties[~us_counties["STATEFP"].isin(states2drop_fp)]
epa_ipm_shape_path = Path(Path.cwd(), "rawdata", "epa-2023-reference-case", "ipm_v6_regions.zip")
epa = gpd.read_file(epa_ipm_shape_path, crs="EPSG:4326")
epa = epa.to_crs(us_states.crs)

# --- 2. PREPARE TRANSMISSION DATA ---
print("Processing transmission capacity data...")
epa_centroid = epa.copy()
epa_centroid["CENTROID"] = epa_centroid.geometry.centroid
epa_trans_limits = pd.read_csv(Path(Path.cwd(), "data", "transport_cap_all.csv"))
epa_trans_limits.rename({"TTC_Capacity_2028": "MW"}, axis=1, inplace=True)
epa_trans_limits = epa_trans_limits.loc[(epa_trans_limits["From"].isin(np.unique(epa.IPM_Region))) & (epa_trans_limits["To"].isin(np.unique(epa.IPM_Region)))]
from_to = epa_trans_limits["From"] + "#" + epa_trans_limits["To"]
to_from = epa_trans_limits["To"] + "#" + epa_trans_limits["From"]
unique_pairs = pd.Series(list(from_to.unique()) + list(to_from.unique())).unique()
epa_trans_limits_symmetric = pd.DataFrame(unique_pairs, columns=["FROM_TO"])
epa_trans_limits_symmetric[["From", "To"]] = epa_trans_limits_symmetric["FROM_TO"].str.split("#", expand=True)

def get_avg_mw(row, df):
    from_r, to_r = row["From"], row["To"]
    mask = ((df["From"] == from_r) & (df["To"] == to_r)) | ((df["From"] == to_r) & (df["To"] == from_r))
    return df.loc[mask, "MW"].mean()

epa_trans_limits_symmetric["MW"] = epa_trans_limits_symmetric.apply(get_avg_mw, df=epa_trans_limits, axis=1)
epa_trans_limits_symmetric.dropna(subset=["MW"], inplace=True)
epa_trans_limits_symmetric = epa_trans_limits_symmetric[epa_trans_limits_symmetric.MW > 0].reset_index(drop=True)

# --- 3. CLASSIFY AND STYLE THE LINES ---
print(f"Classifying lines based on REGION_PREFIX: '{REGION_PREFIX}'...")
def classify_line(row, prefix):
    from_in, to_in = row['From'].strip().startswith(prefix), row['To'].strip().startswith(prefix)
    if from_in and to_in: return 'internal'
    elif from_in or to_in: return 'interface'
    else: return 'external'

epa_trans_limits_symmetric['line_type'] = epa_trans_limits_symmetric.apply(classify_line, prefix=REGION_PREFIX, axis=1)
style_map = {
    'internal':  {'color': 'green', 'alpha': 0.9, 'zorder': 12},
    'interface': {'color': 'red',   'alpha': 0.9, 'zorder': 11},
    'external':  {'color': 'grey',  'alpha': 0.4, 'zorder': 10}
}
centroids_map = epa_centroid.set_index('IPM_Region')['CENTROID']
epa_trans_limits_symmetric['FROM_CENTROID'] = epa_trans_limits_symmetric['From'].map(centroids_map)
epa_trans_limits_symmetric['TO_CENTROID'] = epa_trans_limits_symmetric['To'].map(centroids_map)
epa_trans_limits_symmetric["linewidth"] = 5 * epa_trans_limits_symmetric["MW"] / max(epa_trans_limits_symmetric["MW"])

# --- Create a centralized color map for all IPM regions ---
unique_regions = sorted(epa["IPM_Region"].unique())
colors = generate_colormap(len(unique_regions))
color_map_dict = dict(zip(unique_regions, colors))
main_cmap = ListedColormap(colors)

# --- 4. GENERATE THE PLOT ---
print("Generating plot...")
fig, (ax_main, ax_inset) = plt.subplots(
    nrows=2,
    ncols=1,
    figsize=(12, 18),
    gridspec_kw={'height_ratios': [3, 2]}
)
fig.suptitle(f"US Transmission Capacity Map with {REGION_PREFIX} Inset", fontsize=16)

# --- Plot basemap on the TOP axes (ax_main) ---
us_counties.boundary.plot(ax=ax_main, edgecolor="grey", linewidth=0.2, zorder=2)
us_states.boundary.plot(ax=ax_main, edgecolor="black", linewidth=0.6, zorder=3)
epa.plot(ax=ax_main, column="IPM_Region", categorical=True, cmap=main_cmap, edgecolor="black", linewidth=0.7, alpha=0.3, zorder=1)

# --- Plot transmission lines on the TOP axes (ax_main) ---
for idx, row in epa_trans_limits_symmetric.iterrows():
    from_point, to_point = row["FROM_CENTROID"], row["TO_CENTROID"]
    line_style = style_map.get(row['line_type'], {'color': 'black', 'alpha': 0.5, 'zorder': 9})
    if from_point and to_point:
        line = Line2D([from_point.x, to_point.x], [from_point.y, to_point.y], linewidth=row["linewidth"], solid_capstyle='round', **line_style)
        ax_main.add_line(line)

# --- Plot nodes on the TOP axes (ax_main) ---
nodes_gdf = gpd.GeoDataFrame(epa_centroid.drop(columns='geometry'), geometry=epa_centroid['CENTROID'])
nodes_gdf.plot(ax=ax_main, color='black', markersize=25, edgecolor='white', linewidth=0.5, zorder=15)

# --- Set up legend and title for the TOP axes (ax_main) ---
legend_elements = [
    Line2D([0], [0], color='green', lw=3, label=f'Internal Lines ({REGION_PREFIX})'),
    Line2D([0], [0], color='red', lw=3, label='Interface Lines'),
    Line2D([0], [0], color='grey', lw=3, label='External Lines'),
    Line2D([0], [0], marker='o', color='w', label='Region Node', markerfacecolor='black', markeredgecolor='white', markersize=8)
]
ax_main.legend(handles=legend_elements, loc='lower right', title='Map Legend')
ax_main.set_title("National View", loc="center")
ax_main.set_axis_off()

# --- Plot data for the selected region on the BOTTOM axes (ax_inset) ---
print(f"Creating {REGION_PREFIX} inset plot...")
inset_regions = epa[epa['IPM_Region'].str.startswith(REGION_PREFIX)].copy()
inset_lines = epa_trans_limits_symmetric[epa_trans_limits_symmetric['line_type'] == 'internal']
# --- MODIFICATION: Filter for interface lines connected to the inset region ---
interface_lines_for_inset = epa_trans_limits_symmetric[
    (epa_trans_limits_symmetric['line_type'] == 'interface') &
    (epa_trans_limits_symmetric['From'].str.startswith(REGION_PREFIX) | epa_trans_limits_symmetric['To'].str.startswith(REGION_PREFIX))
]
inset_nodes = nodes_gdf[nodes_gdf['IPM_Region'].str.startswith(REGION_PREFIX)]

inset_boundary = inset_regions.unary_union
inset_states = gpd.clip(us_states, inset_boundary)
inset_counties = gpd.clip(us_counties, inset_boundary)

inset_regions['color'] = inset_regions['IPM_Region'].map(color_map_dict)
inset_regions.plot(ax=ax_inset, color=inset_regions['color'], edgecolor="black", linewidth=0.7, alpha=0.5, zorder=1)

inset_counties.boundary.plot(ax=ax_inset, edgecolor="grey", linewidth=0.2, zorder=2)
inset_states.boundary.plot(ax=ax_inset, edgecolor="black", linewidth=1.5, zorder=3)

for idx, row in inset_states.iterrows():
    point = row.geometry.representative_point()
    if 'STUSPS' in inset_states.columns and row.geometry.area > 0:
        ax_inset.text(
            point.x,
            point.y,
            row['STUSPS'],
            fontsize=12,
            fontweight='bold',
            ha='center',
            va='center',
            color='black',
            path_effects=[pe.withStroke(linewidth=3, foreground='white', alpha=0.7)]
        )

# Plot INTERNAL (green) lines on inset
for idx, row in inset_lines.iterrows():
    from_point, to_point = row["FROM_CENTROID"], row["TO_CENTROID"]
    line_style = style_map.get('internal')
    if from_point and to_point:
        line = Line2D([from_point.x, to_point.x], [from_point.y, to_point.y], linewidth=row["linewidth"], solid_capstyle='round', **line_style)
        ax_inset.add_line(line)

# --- MODIFICATION: Plot INTERFACE (red) lines and prepare for external state labels ---
external_connection_points = {} # To store unique external points for labeling
for idx, row in interface_lines_for_inset.iterrows():
    from_point, to_point = row["FROM_CENTROID"], row["TO_CENTROID"]
    line_style = style_map.get('interface')
    if from_point and to_point:
        line = Line2D([from_point.x, to_point.x], [from_point.y, to_point.y], linewidth=row["linewidth"], solid_capstyle='round', **line_style)
        ax_inset.add_line(line)
        
        # Identify the external point and region name
        if row['From'].strip().startswith(REGION_PREFIX):
            external_point, external_region_name = to_point, row['To']
        else:
            external_point, external_region_name = from_point, row['From']
        
        # Store unique external points to avoid duplicate labels
        if external_region_name not in external_connection_points:
            external_connection_points[external_region_name] = external_point

# --- MODIFICATION: Add labels for states connected via interface lines ---
if external_connection_points:
    external_nodes_df = pd.DataFrame(list(external_connection_points.items()), columns=['IPM_Region', 'geometry'])
    external_nodes_gdf = gpd.GeoDataFrame(external_nodes_df, geometry='geometry', crs=us_states.crs)

    # Find which state each external node is in
    external_states_info = gpd.sjoin(external_nodes_gdf, us_states[['STUSPS', 'geometry']], how='left', predicate='within')
    external_states_info.drop_duplicates(subset='STUSPS', inplace=True) # Label each state only once

    for idx, row in external_states_info.iterrows():
        point, state_abbr = row.geometry, row['STUSPS']
        if pd.notna(state_abbr):
            ax_inset.text(
                point.x, point.y, state_abbr, fontsize=14, fontweight='bold', ha='center', va='center',
                color='darkred', path_effects=[pe.withStroke(linewidth=3.5, foreground='white', alpha=0.8)]
            )

inset_nodes.plot(ax=ax_inset, color='black', markersize=25, edgecolor='white', linewidth=0.5, zorder=15)

# --- MODIFICATION: Add a legend for the IPM region colors to the inset plot ---
inset_region_names = sorted(inset_regions['IPM_Region'].unique())
region_legend_elements = [Patch(facecolor=color_map_dict[name], edgecolor='black', label=name)
                          for name in inset_region_names]
ax_inset.legend(handles=region_legend_elements,
                loc='upper left',
                title=f'{REGION_PREFIX} Regions',
                fontsize='medium',
                bbox_to_anchor=(1.02, 1), # Place legend outside the plot area
                borderaxespad=0.)

bounds = inset_regions.total_bounds
x_margin, y_margin = (bounds[2] - bounds[0]) * 0.1, (bounds[3] - bounds[1]) * 0.1
ax_inset.set_xlim(bounds[0] - x_margin, bounds[2] + x_margin)
ax_inset.set_ylim(bounds[1] - y_margin, bounds[3] + y_margin)

ax_inset.set_title(f"{REGION_PREFIX} Region Detail", loc="center")
ax_inset.set_axis_off()
for spine in ax_inset.spines.values():
    spine.set_edgecolor('black')
    spine.set_linewidth(1.0)

# --- Final plot adjustments ---
# --- MODIFICATION: Adjust layout to make space for the new legend and reduce top whitespace ---
plt.tight_layout(rect=[0, 0, 0.85, 0.95])

# --- Save the figure ---
# Ensure the 'figures' directory exists before saving
output_dir = Path(Path.cwd(), "figures")
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / f"epa_ipm_trans_limits_{REGION_PREFIX}.png"
plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1, facecolor='w')
print(f"\nPlot saved successfully to:\n{output_path}")

plt.show()