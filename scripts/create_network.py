# Copyright 2019-2020 Martha Frysztacki (KIT)

import pypsa
import pandas as pd

import logging


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    
    bus = pd.read_csv(snakemake.input['buses'], index_col=0)

    branch = pd.read_csv(snakemake.input['lines'], index_col=0)
    dcline = pd.read_csv(snakemake.input['links'], index_col=0)
    
    plant = pd.read_csv(snakemake.input['plants'], index_col=0)
    plant = plant.rename({'bus_id': 'bus'}, axis=1)
    
    #demand = pd.read_csv(data_path + 'demand.csv', index_col=0)
    #zone = pd.read_csv(data_path + 'zone.csv', index_col=0)

    n = pypsa.Network()

    logger.info(f"Adding {len(bus)} buses to the network.")
    n.madd("Bus", bus.index,
           Pd=bus.Pd,
           type=bus.type,
           v_nom=bus.baseKV,
           zone_id=bus.zone_id)

    for tech in ["Line", "Transformer"]:
        branch_tech = branch.query("branch_device_type == @tech")
        logger.info(f"Adding {len(branch_tech)} branches as {tech}s to the network.")
        n.madd(tech, branch_tech.index,
               bus0=branch_tech.from_bus_id, bus1=branch_tech.to_bus_id,
               r=branch_tech.r, x=branch_tech.r,
               s_nom=branch_tech.rateA,
               interconnect=branch_tech.interconnect)

    logger.info(f"Adding {len(dcline)} dc-lines as Links to the network.")
    n.madd("Link", dcline.index,
           bus0=dcline.from_bus_id, bus1=dcline.to_bus_id,
           p_nom=dcline.Pt)

    logger.info(f"Adding {len(plant)} Generators to the network.")
    n.madd("Generator", plant.index,
           bus=plant.bus,
           p_nom=plant.Pmax,
           marginal_cost=plant.GenFuelCost,
    )

    n.lines.length = 1000 #FIX!!
    n.links.length = 1000 #FIX!!

    n.export_to_netcdf(snakemake.output[0])
