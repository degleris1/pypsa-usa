# BY PyPSA-USA Authors 
"""

**Relevant Settings**

.. code:: yaml

    interconnect:
    offshore_shape:
    aggregation_zones:
    countries:


**Inputs**

- ``data/breakthrough_network/base_grid/{interconnect}/bus.csv``
- ``data/breakthrough_network/base_grid/{interconnect}/branch.csv``
- ``data/breakthrough_network/base_grid/{interconnect}/dcline.csv``
- ``data/breakthrough_network/base_grid/{interconnect}/bus2sub.csv``
- ``data/breakthrough_network/base_grid/{interconnect}/sub.csv``
- ``resources/country_shapes.geojson``: confer :ref:`shapes`
- ``resources/offshore_shapes.geojson``: confer :ref:`shapes`
- ``resources/{interconnect}/state_boundaries.geojson``: confer :ref:`shapes`


**Outputs**

- ``networks/base.nc``: 
- ``data/breakthrough_network/base_grid/{interconnect}/bus2sub.csv``
- ``data/breakthrough_network/base_grid/{interconnect}/sub.csv``
- ``resources/{interconnect}/elec_base_network.nc``


**Description**

Reads in Breakthrough Energy/TAMU transmission dataset, and converts it into PyPSA compatible components. A base netowork file (`*.nc`) is written out. Included in this network are: 
    - Geolocated buses 
    - Geoloactated AC and DC transmission lines + links
    - Transformers 

"""


import pypsa, pandas as pd, logging, geopandas as gpd
from geopandas.tools import sjoin
from _helpers import configure_logging
from pypsa.geo import haversine

idx = pd.IndexSlice

def add_buses_from_file(n: pypsa.Network, buses: gpd.GeoDataFrame, interconnect: str) -> pypsa.Network:
    if interconnect != "usa":
        buses = buses.query(
            "interconnect == @interconnect"
        )

    logger.info(f"Adding {len(buses)} buses to the network.")

    n.madd(
        "Bus",
        buses.index,
        Pd = buses.Pd, # used to decompose zone demand to bus demand
        v_nom = buses.baseKV,
        zone_id = buses.zone_id,
        balancing_area = buses.balancing_area,
        state = buses.state,
        country = buses.country,
        interconnect = buses.interconnect,
        x = buses.lon,
        y = buses.lat,
        sub_id = buses.sub_id
    )

    return n

def add_branches_from_file(n: pypsa.Network, fn_branches: str) -> pypsa.Network:

    branches = pd.read_csv(
        fn_branches, dtype={"from_bus_id": str, "to_bus_id": str}, index_col=0
    ).query("from_bus_id in @n.buses.index and to_bus_id in @n.buses.index")

    for tech in ["Line", "Transformer"]:
        tech_branches = branches.query("branch_device_type == @tech")
        logger.info(f"Adding {len(tech_branches)} branches as {tech}s to the network.")

        # S_base = 100 MVA
        n.madd( 
            tech,
            tech_branches.index,
            bus0=tech_branches.from_bus_id,
            bus1=tech_branches.to_bus_id,
            r=tech_branches.r
            * (n.buses.loc[tech_branches.from_bus_id]["v_nom"].values ** 2)
            / 100,
            x=tech_branches.x
            * (n.buses.loc[tech_branches.from_bus_id]["v_nom"].values ** 2)
            / 100,
            b=tech_branches.b
            / (n.buses.loc[tech_branches.from_bus_id]["v_nom"].values ** 2),
            s_nom=tech_branches.rateA,
            v_nom=tech_branches.from_bus_id.map(n.buses.v_nom),
            interconnect=tech_branches.interconnect,
            type="Rail", #rail is used temporarily then over ridden by assign_line_types
            carrier="AC"
        )
    return n

def add_custom_line_type(n: pypsa.Network):
    n.line_types.loc["Rail"] = pd.Series(
        [60, 0.0683, 0.335, 15, 1.01],
        index=["f_nom", "r_per_length", "x_per_length", "c_per_length", "i_nom"],
    )

def assign_line_types(n: pypsa.Network):
    n.lines.type = n.lines.v_nom.map(snakemake.config['lines']['types'])

def add_dclines_from_file(n: pypsa.Network, fn_dclines: str) -> pypsa.Network:

    dclines = pd.read_csv(
        fn_dclines, dtype={"from_bus_id": str, "to_bus_id": str}, index_col=0
    ).query("from_bus_id in @n.buses.index and to_bus_id in @n.buses.index")

    logger.info(f"Adding {len(dclines)} dc-lines as Links to the network.")

    n.madd(
        "Link",
        dclines.index,
        bus0=dclines.from_bus_id,
        bus1=dclines.to_bus_id,
        p_nom=dclines.Pt,
        carrier="DC",
        underwater_fraction=0.0, #DC line in bay is underwater, but does network have this line?
    )

    return n

def assign_sub_id(buses: pd.DataFrame, bus_locs: pd.DataFrame) -> pd.DataFrame:
    """Adds sub id to dataframe as a new column"""
    buses['sub_id'] = bus_locs.sub_id
    return buses

def assign_bus_location(buses: pd.DataFrame, buslocs: pd.DataFrame) -> gpd.GeoDataFrame:
    """Attaches coordinates and sub ids to each bus"""
    gdf_bus = pd.merge(buses, buslocs[['lat','lon']], left_index=True, right_index=True, how='left')
    gdf_bus["geometry"] = gpd.points_from_xy(gdf_bus["lon"], gdf_bus["lat"])
    return gpd.GeoDataFrame(gdf_bus, crs=4326)
    
def map_bus_to_region(buses: gpd.GeoDataFrame, shape: gpd.GeoDataFrame, name: str) -> gpd.GeoDataFrame:
    """Maps a bus to a geographic region
    
    Args:
        buses: gpd.GeoDataFrame, 
        shape: gpd.GeoDataFrame, 
        name: str
            column name in shape to merge
    """
    shape_filtered = shape[[name, "geometry"]]
    return gpd.sjoin(buses, shape_filtered, how="left").drop(columns=["index_right"])

def assign_line_length(n: pypsa.Network):
    '''Assigns line length to each line in the network using Haversine distance'''
    bus_df = n.buses[['x','y']]
    distances = haversine(bus_df.loc[n.lines.bus0].values, bus_df.loc[n.lines.bus1].values)
    n.lines['length'] = distances[:,0]
    n.lines.length.plot(kind='hist', bins=100)


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    if 'snakemake' not in globals():
        from _helpers import mock_snakemake
        snakemake = mock_snakemake('build_base_network', interconnect='western')
    configure_logging(snakemake)

    # create network
    n = pypsa.Network()

    interconnect = snakemake.wildcards.interconnect
    # interconnect in raw data given with an uppercase first letter
    if interconnect != "usa":
        interconnect = interconnect[0].upper() + interconnect[1:]

    #assign locations and balancing authorities to buses
    bus2sub = pd.read_csv(snakemake.input.bus2sub).set_index("bus_id")
    sub = pd.read_csv(snakemake.input.sub).set_index("sub_id")
    buslocs = pd.merge(bus2sub, sub, left_on="sub_id", right_index=True)
 
    # merge bus data with geometry data
    df_bus = pd.read_csv(snakemake.input["buses"], index_col=0)
    df_bus = assign_sub_id(df_bus, buslocs)
    gdf_bus = assign_bus_location(df_bus, buslocs)

    # balancing authority shape
    ba_region_shapes = gpd.read_file(snakemake.input["onshore_shapes"])
    offshore_shapes = gpd.read_file(snakemake.input["offshore_shapes"])
    ba_shape = gpd.GeoDataFrame(pd.concat([ba_region_shapes, offshore_shapes],ignore_index=True))
    ba_shape = ba_shape.rename(columns={"name":"balancing_area"})

    # country and state shapes
    state_shape = gpd.read_file(snakemake.input["state_shapes"])
    state_shape = state_shape.rename(columns={"name":"state"})

    #assign ba, state, and country to each bus
    gdf_bus = map_bus_to_region(gdf_bus, ba_shape, "balancing_area")
    gdf_bus = map_bus_to_region(gdf_bus, state_shape, "state")
    gdf_bus = map_bus_to_region(gdf_bus, state_shape, "country")
    
    # add buses, transformers, lines and links
    n = add_buses_from_file(n, gdf_bus, interconnect=interconnect)
    n = add_branches_from_file(n, snakemake.input["lines"])
    n = add_dclines_from_file(n, snakemake.input["links"])
    add_custom_line_type(n)
    assign_line_types(n)
    assign_line_length(n)
    
    # export bus2sub interconnect data
    logger.info(f"exporting bus2sub and sub data for {interconnect}")
    if interconnect == "usa": #if usa interconnect do not filter bc all sub are in usa
        bus2sub = (
            pd.read_csv(snakemake.input.bus2sub)
            .set_index("bus_id")
        )
        bus2sub.to_csv(snakemake.output.bus2sub)
    else:
        bus2sub = (
            pd.read_csv(snakemake.input.bus2sub)
            .query("interconnect == @interconnect")
            .set_index("bus_id")
        )
        bus2sub.to_csv(snakemake.output.bus2sub)

    # export sub interconnect data
    if interconnect == "usa": #if usa interconnect do not filter bc all sub are in usa
        sub = (
            pd.read_csv(snakemake.input.sub)
            .set_index("sub_id")
        )
        sub.to_csv(snakemake.output.sub)
    else:
        sub = (
            pd.read_csv(snakemake.input.sub)
            .query("interconnect == @interconnect")
            .set_index("sub_id")
        )
        sub.to_csv(snakemake.output.sub)


    # export network
    n.export_to_netcdf(snakemake.output.network)



'''
# Items from build_bus_regions to be added to this script
        for ba in balancing_areas:

            n.buses.loc[ba_locs.index, 'country'] = ba #adds abbreviation to the bus dataframe under the country column
            n.buses.loc['37584', 'country'] = 'CISO-SDGE'   #hot fix for imperial beach substation being offshore

        for i in range(len(offshore_shapes)):

            n.buses.loc[offshore_busses.index, 'country'] = shape_name #adds offshore shape name to the bus dataframe under the country column


   
        ### Remove Extra OSW Busses and Branches ###
        #Removes remaining nodes in network left with country = US (these are offshore busses that are not in the offshore shape or onshore shapes)

        #To-do- add filter that checks if the buses being removed are over water. Currently this works for WECC since I have cleaned up the GEOJSON files
        n.mremove("Line", n.lines.loc[n.lines.bus1.isin(n.buses.loc[n.buses.country=='US'].index)].index) 
        n.mremove("Load", n.loads.loc[n.loads.bus.isin(n.buses.loc[n.buses.country=='US'].index)].index)
        n.mremove("Generator", n.generators.loc[n.generators.bus.isin(n.buses.loc[n.buses.country=='US'].index)].index)
        n.mremove("Bus",  n.buses.loc[n.buses.country=='US'].index)

'''