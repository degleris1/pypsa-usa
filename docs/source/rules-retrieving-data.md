# Retrieve Data

Numerous datasets used in PyPSA USA are large and are not stored on GitHub. Insted, data is stored on Zenodo or supplier websites, and the workflow will automatically download these datasets via the `retrieve` rules

(databundle)=
## Rule `retrieve_zenodo_databundles`

Data used to create the base electrical network is pulled from [Breakthrough Energy](https://breakthroughenergy.org/) (~4.3GB). This includes geolocated data on substations, power lines, generators, electrical demand, and resource potentials. 

[![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.4538590.svg)](https://zenodo.org/record/4538590)

Protected land area data for the USA is retrieved from [Protected Planet](https://www.protectedplanet.net/en) via the [PyPSA Meets-Earth](https://pypsa-meets-earth.github.io/) data deposit (`natura_global`) (~100MB). 

[![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.10067222.svg)](https://zenodo.org/records/10067222)

Baythymetry data via [GEBCO](https://www.gebco.net/) and a cutout of USA [Copernicus Global Land Service](https://land.copernicus.eu/global/products/lc) data are downloaded from a PyPSA USA Zenodo depost (~2GB). 

[![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.10067222.svg)](https://zenodo.org/records/10067222)

(databundle-sector)=
## Rule `retrieve_sector_databundle`
Retrives data for sector coupling

[![DOI](https://sandbox.zenodo.org/badge/DOI/10.5072/zenodo.10019422.svg)](https://zenodo.org/records/10019422)

Geographic boundaries of the United States counties are taken from the 
United States Census Bureau. Note, these follow 2020 boundaries to match 
census numbers 

[![URL](https://img.shields.io/badge/URL-Cartographic_Boundaries-blue)](<https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.2020.html#list-tab-1883739534>)

County level populations are taken from the United States Census Bureau. Filters applied:
 - Geography: All Counties within United States and Puerto Rico
 - Year: 2020
 - Surveys: Decennial Census, Demographic and Housing Characteristics
 
Sheet Name: Decennial Census - P1 | Total Population - 2020: DEC Demographic and Housing Characteristics

[![URL](https://img.shields.io/badge/URL-United_States_Census_Bureau-blue)](<https://data.census.gov/>)

County level urbanization rates are taken from the United States Census Bureau. Filters applied:
 - Geography: All Counties within United States and Puerto Rico
 - Year: 2020
 - Surveys: Decennial Census, Demographic and Housing Characteristics
 
Sheet Name: Decennial Census - H1 | Housing Units - 2020: DEC Demographic and Housing Characteristics

[![URL](https://img.shields.io/badge/URL-United_States_Census_Bureau-blue)](<https://data.census.gov/>)

(retrieve-eia)=
## Rule `retrieve_eia_data`

Historical electrical load data from 2015 till the last present month are retrieved from the [US Energy Information Agency](https://www.eia.gov/) (EIA). Data is downloaded at hourly temporal resolution and at a spatial resolution of balancing authority region. 

(retrieve-wecc)=
## Rule `retrieve_WECC_forcast_data`

Forecasted electricity demand data and generator operational charasteristics for the [Western Electricity Coordinating Council](https://www.wecc.org/Pages/home.aspx) (WECC) region are retrieved directly from WECC. Projected data for both 2030 and 2032 are retrieved (~300MB each). 

[![URL](https://img.shields.io/badge/URL-WECC_Data-blue)](<https://www.wecc.org/Reliability/Forms/Default%20View.aspx>)

(retrieve-cutout)=
## Rule `retrieve_cutout`

Cutouts are spatio-temporal subsets of the USA weather data from the [ERA5 dataset](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels?tab=overview). They have been prepared by and are for use with the [atlite](https://github.com/PyPSA/atlite) tool. You can either generate them yourself using the build_cutouts rule or retrieve them directly from zenodo through the rule `retrieve_cutout`.

[![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.10067222.svg)](https://zenodo.org/records/10067222)

```{note}
Only the 2019 interconnects based on ERA5 have been prepared and saved to Zenodo for download
```

(costs)=
## Rule `retrieve_cost_data`

This rule downloads economic assumptions from various sources. 

The [NREL](https://www.nrel.gov/) [Annual Technology Baseline](https://atb.nrel.gov/) provides economic parameters on capital costs, fixed operation costs, variable operating costs, fuel costs, technology specific discount rates, average capacity factors, and efficiencies.  

[![URL](https://img.shields.io/badge/URL-NREL_ATB-blue)](<https://atb.nrel.gov/x>)

[![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=ATB%2F)

State level capital cost supply side generator cost multipliers are pulled from the "Capital Cost and Performance
Characteristic Estimates for Utility Scale Electric Power Generating Technologies" by the [EIA](https://www.eia.gov/). Note, these have been saved as CSV's and come with the repository download 

[![URL](https://img.shields.io/badge/URL-CAPEX_Multipliers-blue)](<https://www.eia.gov/analysis/studies/powerplants/capitalcost/pdf/capital_cost_AEO2020.pdf>)

State level historial monthly fuel prices are taken from the [EIA](https://www.eia.gov/). This includes seperate prices for electrical power producers, industrial customers, commercial customers, and residential customers. 

[![URL](https://img.shields.io/badge/URL-EIA_Natural_Gas_Prices-blue)](<https://www.eia.gov/dnav/ng/ng_pri_sum_dcu_nus_m.htm>)

The [Annual Technology Baseline](https://atb.nrel.gov/) also provides data on the [transportation sector](https://atb.nrel.gov/transportation/2020/index), including fuel usage and capital costs.   

[![URL](https://img.shields.io/badge/URL-NREL_ATB_Transportation-blue)](<https://atb.nrel.gov/transportation/2020/index>)

To populate any missing data, the [PyPSA/technology-data](https://github.com/PyPSA/technology-data) project is used. Data from here 
is only used when no other sources can be found, as it is mostly European focused. 

[![GitHub](https://img.shields.io/badge/github-%23121011.svg?style=for-the-badge&logo=github&logoColor=white)](https://github.com/PyPSA/technology-data)

**Relevant Settings** 

```yaml
enable:
    retrieve_cost_data:

costs:
    year:
    version:
```

```{seealso}
Documentation of the configuration file ``config/config.yaml`` at
:ref:`costs_cf`
```

**Outputs** 

- ``resources/costs.csv``
