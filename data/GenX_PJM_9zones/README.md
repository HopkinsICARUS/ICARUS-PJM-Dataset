# PJM 9 Zone Model

We adopted [GenX’s `1_three_zones` example](https://github.com/GenXProject/GenX.jl/tree/main/example_systems/1_three_zones) to build the **GenX-formatted PJM 9 Zone Model**. All relevant data are updated from the [ICARUS PJM Data](https://github.com/HopkinsICARUS/ICARUS-PJM-Dataset/tree/main/data/PJM); default GenX values are retained where data were unavailable.

For **VRE (`resources/Vre.csv`)**, we aggregated existing wind and solar by PJM region and state, and further split them into RES and resource classes. Default `Inv_Cost_per_MWyr` and `Fixed_OM_Cost_per_MWyr` values are retained from GenX. Offshore wind costs are scaled: **3× onshore** for fixed-bottom and **5× onshore** for floating. 

Detailed generation profiles are provided in `system/Generators_variability.csv`, where thermal generators are ignored to have be default 1. Since `PJM_ATSI_PA_SolarPV` was missing in the raw data (`solar.csv`), it is replaced with `PJM_ATSI_OH_SolarPV`.

We provide constant and fuel-specific emission factors (`system/Fuels_data.csv`), ignoring multiple-fuel capability for simplicity. **Storage** combines batteries and pumped hydro in `resources/Storage.csv`, consistent with GenX conventions.