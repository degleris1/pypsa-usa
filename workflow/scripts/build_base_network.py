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
import numpy as np
from shapely.geometry import Polygon, Point
import geopandas as gpd
from shapely.geometry import Point
from sklearn.neighbors import BallTree
import constants as const


def haversine_np(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    
    All args must be of equal length.    
    source: https://stackoverflow.com/questions/29545704/fast-haversine-approximation-python-pandas
    """
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6378.137 * c
    return km


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
        sub_id = buses.sub_id,
        substation_off = False,
        poi = False
    )

    n.buses.loc[n.buses.sub_id.astype(int) >= 41012, 'substation_off'] = True #mark offshore buses
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
            type="temp", #temporarily then over ridden by assign_line_types
            carrier="AC",
            underwater_fraction=0.0,
        )
    return n


def add_custom_line_type(n: pypsa.Network):
    n.line_types.loc["temp"] = pd.Series(
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
    bus0 = bus_df.loc[n.lines.bus0].values
    bus1 = bus_df.loc[n.lines.bus1].values
    distances = haversine_np(bus0[:,0], bus0[:,1], bus1[:,0], bus1[:,1])
    n.lines['length'] = distances


def create_grid(polygon, cell_size):
    """
    Creates a grid of square cells over a given polygon and returns the centers of the cells.
    
    :param polygon: A Shapely Polygon object.
    :param cell_size: The length of each side of the square cells.
    :return: List of (latitude, longitude) tuples for the center of each cell.
    """
    minx, miny, maxx, maxy = polygon.bounds
    grid_cells = []

    # Create the grid cells
    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            grid_cells.append(Polygon([(x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)]))
            y += cell_size
        x += cell_size

    # Convert to a GeoDataFrame
    grid_gdf = gpd.GeoDataFrame(geometry=grid_cells)

    # Filter to only those cells that intersect the polygon
    intersecting_cells = grid_gdf[grid_gdf.intersects(polygon)]

    # Find the center of each cell
    centers = intersecting_cells.geometry.centroid

    # Return the coordinates of the centers
    return [(center.y, center.x) for center in centers]


def build_offshore_buses(offshore_shapes: gpd.GeoDataFrame) -> pd.DataFrame:
    "Build dataframe of offshore buses by creating evenly spaced grid cells inside of the offshore shapes."
    offshore_buses = pd.DataFrame()
    offshore_shapes = offshore_shapes.to_crs('EPSG:5070')
    for shape in offshore_shapes.geometry:
        cell_centers = create_grid(shape, 25e3) # 25km cell size
        cell_centers = pd.DataFrame(cell_centers, columns=['lat', 'lon'])
        offshore_buses = pd.concat([offshore_buses, cell_centers], ignore_index=True)
    #reproject back to EPSG:4326
    offshore_buses = gpd.GeoDataFrame(offshore_buses, geometry=gpd.points_from_xy(offshore_buses.lon, offshore_buses.lat), crs='EPSG:5070')
    offshore_buses = offshore_buses.to_crs('EPSG:4326')
    offshore_buses.lat = offshore_buses.geometry.y
    offshore_buses.lon = offshore_buses.geometry.x
    offshore_buses['sub_id'] = np.arange(50000, 50000+len(offshore_buses))
    offshore_buses.index = np.arange(3008161, 3008161+len(offshore_buses))
    return offshore_buses

def add_offshore_buses(n: pypsa.Network, offshore_buses: pd.DataFrame) -> pypsa.Network:
    "Add offshore buses to network"
    n.madd(
        "Bus",
        offshore_buses.index,
        Pd = 0,
        v_nom = 230,
        balancing_area = 'Offshore',
        state = 'Offshore',
        country = 'US',
        interconnect = 'Offshore',
        x = offshore_buses.lon,
        y = offshore_buses.lat,
        sub_id = offshore_buses.sub_id.astype(str),
        substation_off = True,
        poi_sub = False,
        poi_bus = False
    )
    return n


def assign_texas_poi(n: pypsa.Network) -> pypsa.Network:
    tx_pois_sub = [40893, 40894, 40729, 40908, 40854, 40760, 40776]
    tx_pois_bus = [3007405, 3007407, 3007096, 3007429, 3007321, 3007171, 3007205]
    n.buses.loc[n.buses.sub_id.isin(tx_pois_sub), 'poi_sub'] = True
    n.buses.loc[n.buses.sub_id.isin(tx_pois_bus), 'poi_bus'] = True
    return n


def identify_osw_poi(n: pypsa.Network) -> pypsa.Network:
    "Identify offshore wind points of interconnections in the base network."
    offshore_lines = n.lines.loc[n.lines.bus0.isin(n.buses.loc[n.buses.substation_off].index)]
    poi_bus_ids = offshore_lines.bus1.unique()
    poi_sub_ids = n.buses.loc[poi_bus_ids, 'sub_id'].unique()
    n.buses.loc[n.buses.index.isin(poi_bus_ids), 'poi_bus'] = True
    n.buses.loc[n.buses.sub_id.isin(poi_sub_ids), 'poi_sub'] = True
    n.buses.poi_bus = n.buses.poi_bus.fillna(False)
    n.buses.poi_sub = n.buses.poi_sub.fillna(False)
    return n


def match_osw_to_poi(buses_to_match_to, missing_buses):
    missing_buses = missing_buses.copy()
    missing_buses['bus_assignment'] = None

    buses_to_match_to['geometry'] = gpd.points_from_xy(buses_to_match_to["x"], buses_to_match_to["y"])

    # from: https://stackoverflow.com/questions/58893719/find-nearest-point-in-other-dataframe-with-a-lot-of-data
    # Create a BallTree 
    tree = BallTree(buses_to_match_to[['x', 'y']].values, leaf_size=2)
    # Query the BallTree on each feature from 'appart' to find the distance
    # to the nearest 'pharma' and its id
    missing_buses['distance_nearest'], missing_buses['id_nearest'] = tree.query(
        missing_buses[['x', 'y']].values, # The input array for the query
        k=1, # The number of nearest neighbors
    )
    missing_buses['bus_assignment'] = buses_to_match_to.reset_index().iloc[missing_buses.id_nearest].Bus.values
    missing_buses.drop(columns=['id_nearest'], inplace=True)
    return missing_buses


def build_offshore_transmission_configuration(n: pypsa.Network) -> pypsa.Network:
    "Builds offshore transmission configurations connecting offshore buses to the POIs onshore."
    poi_buses = n.buses.loc[n.buses.poi_sub] #identify the buses at the POI
    highest_voltage_buses = poi_buses.loc[poi_buses.groupby('sub_id')['v_nom'].idxmax()]
    offshore_buses = match_osw_to_poi(highest_voltage_buses, n.buses.loc[n.buses.substation_off]) #match offshore buses to POI

    osw_offsub_bus_ids = n.buses.loc[n.buses.substation_off].index

    line_lengths = haversine_np(n.buses.loc[offshore_buses.bus_assignment].x.values, 
                                n.buses.loc[offshore_buses.bus_assignment].y.values, 
                                offshore_buses.x.values, 
                                offshore_buses.y.values
                            )
    # add onshore poi buses @230kV
    logger.info(f"Adding {len(offshore_buses)} offshore buses to the network.")

    # Reassigns Offshore buses region identifies to the POI bus regions
    n.buses.loc[offshore_buses.index, 'balancing_area'] = n.buses.loc[offshore_buses.bus_assignment].balancing_area.values
    n.buses.loc[offshore_buses.index, 'state'] = n.buses.loc[offshore_buses.bus_assignment].state.values
    n.buses.loc[offshore_buses.index, 'country'] = n.buses.loc[offshore_buses.bus_assignment].country.values
    n.buses.loc[offshore_buses.index, 'interconnect'] = n.buses.loc[offshore_buses.bus_assignment].interconnect.values


    n.madd(
        "Bus",
        "OSW_POI_" + osw_offsub_bus_ids, #name poi bus after offshore substation
        v_nom = 230,
        sub_id = offshore_buses.sub_id.values,
        balancing_area = n.buses.loc[offshore_buses.bus_assignment].balancing_area.values,
        state = n.buses.loc[offshore_buses.bus_assignment].state.values,
        country = 'US',
        interconnect = n.buses.loc[offshore_buses.bus_assignment].interconnect.values,
        x = n.buses.loc[offshore_buses.bus_assignment].x.values,
        y = n.buses.loc[offshore_buses.bus_assignment].y.values,
        poi_bus = True,
        poi_sub = True,
        substation_off = False,
    )

    # add offshore wind export cables
    logger.info(f"Adding offshore wind export lines to the network.")
    n.madd(
        "Line",
        "OSW_export_" + osw_offsub_bus_ids, #name line after offshore substation
        v_nom = 230,
        bus0 = osw_offsub_bus_ids.values,
        bus1 = "OSW_POI_" + osw_offsub_bus_ids.values,
        length = line_lengths,
        type = "temp",
        carrier = "AC",
        x = 0.1,
        r = 0.1,
        s_nom = 5000,
        underwater_fraction = 0.0, #temporarily setting to investigate clustering underwater issues later
        interconnect = n.buses.loc[offshore_buses.bus_assignment].interconnect.values,
    )

    # add offshore transmission transformers
    n.madd(
        "Transformer",
        "OSW_poi_stepup_" + osw_offsub_bus_ids, #name transformer after offshore substation
        bus0 = "OSW_POI_" + osw_offsub_bus_ids,
        bus1 = offshore_buses.bus_assignment.astype(str).values,
        s_nom = 5000,
        type = "temp",
        carrier = "AC",
        v_nom = 230,
        x = 0.1,
        r = 0.1,
    )
    return n


def remove_breakthrough_offshore(n: pypsa.Network) -> pypsa.Network:
    """ Remove Offshore buses, Branches, Transformers, and Generators from the original BE network."""
    #rm any lines/buses associated with offshore substation buses
    n.mremove("Line", n.lines.loc[n.lines.bus0.isin(n.buses.loc[n.buses.substation_off].index)].index)
    n.mremove("Bus",  n.buses.loc[n.buses.substation_off].index)
    return n


def assign_missing_states_countries(n: pypsa.Network):
    """Assign buses missing state and countries to their nearest neighbor bus value"""
    buses = n.buses.copy()
    missing = buses.loc[buses.state.isna() | buses.country.isna() | buses.balancing_area.isna()]
    buses = buses.loc[~buses.state.isna() & ~buses.country.isna() & ~buses.balancing_area.isna()]
    buses = buses.loc[~buses.state.isin(['Offshore'])]
    missing = match_osw_to_poi(buses, missing)
    missing.balancing_area = buses.loc[missing.bus_assignment].balancing_area.values
    missing.state = buses.loc[missing.bus_assignment].state.values
    missing.country = buses.loc[missing.bus_assignment].country.values
    n.buses.loc[missing.index, 'balancing_area'] = missing.balancing_area
    n.buses.loc[missing.index, 'state'] = missing.state
    n.buses.loc[missing.index, 'country'] = missing.country
    n.buses.loc[missing.index, 'interconnect'] = missing.interconnect



def modify_breakthrough_substations(n:pypsa.Network, interconnect:str):
    if interconnect == 'Western':
        sub_fixes = {35017 : {'x':-123.0922,'y':48.5372},
        35033 : {'x':-122.78053,'y':48.65694}, 
        37584 : {'x':-117.10501, 'y':32.54935}}
        for i in sub_fixes.keys():
            n.buses.loc[n.buses.sub_id == i, 'x'] = sub_fixes[i]['x']
            n.buses.loc[n.buses.sub_id == i, 'y'] = sub_fixes[i]['y']
    return n

def main(snakemake):
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
    
    # Removing few duplicated shapes where GIS shapes were overlapping. TODO Fix GIS shapes
    gdf_bus = gdf_bus.reset_index().drop_duplicates(subset='bus_id', keep='first').set_index('bus_id')

    # add buses, transformers, lines and links
    n = add_buses_from_file(n, gdf_bus, interconnect=interconnect)
    n = add_branches_from_file(n, snakemake.input["lines"])
    n = add_dclines_from_file(n, snakemake.input["links"])
    n = modify_breakthrough_substations(n, interconnect)

    # identify offshore points of interconnection, and remove unncess components from BE network
    n = identify_osw_poi(n)
    if interconnect=='Texas': 
        n = assign_texas_poi(n)
    n = remove_breakthrough_offshore(n)

    # build new offshore network configuration
    offshore_buses = build_offshore_buses(offshore_shapes)
    n = add_offshore_buses(n, offshore_buses)
    n = build_offshore_transmission_configuration(n)

    if interconnect=='Eastern': 
        logger.warning(f"Eastern Interconnect is missing {len(n.buses.loc[n.buses.balancing_area.isna() | n.buses.state.isna() | n.buses.country.isna()])} bus locations. Must clean-up GIS files before using!")

    #asssign line types and lengths
    add_custom_line_type(n)
    assign_line_types(n)
    assign_line_length(n)
    assign_missing_states_countries(n)
    
    logger.info(f"Network is missing BA/State/Country information for {len(n.buses.loc[n.buses.balancing_area.isna() | n.buses.state.isna() | n.buses.country.isna()])} buses.")

    # export bus2sub interconnect data
    logger.info(f"Exporting bus2sub and sub data for {interconnect}")

    bus2sub = n.buses[['sub_id', 'interconnect','balancing_area','x','y']]
    bus2sub.to_csv(snakemake.output.bus2sub)
    subs = n.buses[['sub_id', 'x', 'y', 'interconnect']].set_index('sub_id').drop_duplicates().rename(columns={'x':'lon', 'y':'lat'})
    subs.to_csv(snakemake.output.sub)

    # Export GIS Mapping Files
    n.buses.to_csv(snakemake.output.bus_gis)
    lines_gis = n.lines.copy()
    lines_gis['bus0'] = lines_gis.bus0.astype(str)
    lines_gis['bus1'] = lines_gis.bus1.astype(str)
    lines_gis['lat1'] = n.buses.loc[lines_gis.bus0].y.values
    lines_gis['lon1'] = n.buses.loc[lines_gis.bus0].x.values
    lines_gis['lat2'] = n.buses.loc[lines_gis.bus1].y.values
    lines_gis['lon2'] = n.buses.loc[lines_gis.bus1].x.values
    lines_gis['WKT_geometry'] = 'LINESTRING ('+lines_gis.lon1.astype(str).values+' '+lines_gis.lat1.astype(str).values+', '+lines_gis.lon2.astype(str).values+' '+lines_gis.lat2.astype(str).values+')'
    lines_gis.to_csv(snakemake.output.lines_gis)
    # export network
    n.export_to_netcdf(snakemake.output.network)

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    if 'snakemake' not in globals():
        from _helpers import mock_snakemake
        snakemake = mock_snakemake('build_base_network', interconnect='texas')
    configure_logging(snakemake)
    main(snakemake)
