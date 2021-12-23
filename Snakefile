
from os.path import normpath, exists
from shutil import copyfile

from snakemake.remote.HTTP import RemoteProvider as HTTPRemoteProvider
HTTP = HTTPRemoteProvider()

configfile: "config.yaml"


COSTS="data/costs.csv"


wildcard_constraints:
    simpl="[a-zA-Z0-9]*|all",
    clusters="[0-9]+m?|all",
    ll="(v|c)([0-9\.]+|opt|all)|all",
    opts="[-+a-zA-Z0-9\.]*"


datafiles = ['bus.csv', 'sub.csv', 'bus2sub.csv', 'dcline.csv', 'demand.csv',
             'plant.csv', 'solar.csv', 'wind.csv']


if config['enable'].get('retrieve_data', True):
    rule retrieve_databundle:
        output: expand('data/base_grid/{file}', file=datafiles)
        log: "logs/retrieve_databundle.log"
        script: 'scripts/retrieve_databundle.py'


rule create_network:
    input:
        buses='data/base_grid/bus.csv',
        lines='data/base_grid/branch.csv',
        links='data/base_grid/dcline.csv',
        plants='data/base_grid/plant.csv',
        bus2sub='data/base_grid/bus2sub.csv'
    output: "networks/elec.nc"
    log: "logs/create_network.log"
    benchmark: "benchmarks/create_network"
    threads: 1
    resources: mem=500
    script: "scripts/create_network.py"


rule simplify_network:
    input:
        network = "networks/elec.nc",
        bus2sub = "data/base_grid/bus2sub.csv",
        subs    = "data/base_grid/sub.csv",
    output: "networks/elec_s.nc"
    log: "logs/simplify_network"
    benchmark: "benchmarks/simplify_network"
    threads: 1
    resources: mem=500
    script: "scripts/simplify_network.py"

