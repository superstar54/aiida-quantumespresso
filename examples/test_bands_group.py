from aiida_worktree import WorkTree, build_node
from aiida_quantumespresso.worktrees.bands_group import bands_worktree
from aiida.orm import Dict, KpointsData, load_code, load_group, StructureData
from ase.build import bulk
from aiida import load_profile
from copy import deepcopy

load_profile()

atoms = bulk("Si")
structure_si = StructureData(ase=atoms)

code = load_code("qe-7.2-pw@localhost")
paras = Dict(
        {
            "CONTROL": {
                "calculation": "scf",
            },
            "SYSTEM": {
                "ecutwfc": 30,
                "ecutrho": 240,
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.1,
            },
        }
    )
relax_paras = deepcopy(paras)
relax_paras.get_dict()["CONTROL"]["calculation"] = "vc-relax"
bands_paras = deepcopy(paras)
bands_paras.get_dict()["CONTROL"]["calculation"] = "bands"

kpoints = KpointsData()
kpoints.set_kpoints_mesh([1, 1, 1])
# Load the pseudopotential family.
pseudo_family = load_group("SSSP/1.3/PBEsol/efficiency")
pseudos = pseudo_family.get_pseudos(structure=structure_si)
#
metadata = {
    "options": {
        "resources": {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        },
    }
}

bands_inputs = {
                "relax": {
                    "base": {
                        "pw": {
                            "code": code,
                            "pseudos": pseudos,
                            "parameters": relax_paras,
                            "metadata": metadata,
                        },
                        "kpoints": kpoints,
                    },
                },
                "scf": {
                    "pw": {
                        "code": code,
                        "pseudos": pseudos,
                        "parameters": paras,
                        "metadata": metadata,
                    },
                    "kpoints": kpoints,
                },
                "bands": {
                    "pw": {
                        "code": code,
                        "pseudos": pseudos,
                        "parameters": bands_paras,
                        "metadata": metadata,
                    },
                    "kpoints": kpoints,
                },
            }

wt = WorkTree('Bands')
bands_job = wt.nodes.new(bands_worktree, name='bands_group', structure=structure_si, inputs=bands_inputs)
wt.run()
