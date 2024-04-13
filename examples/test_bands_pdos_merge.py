# -*- coding: utf-8 -*-
"""Test."""
from copy import deepcopy

from aiida import load_profile
from aiida.orm import Dict, KpointsData, StructureData, load_code, load_group
from aiida_worktree import WorkTree, build_node
from ase.build import bulk

from aiida_quantumespresso.worktrees.bands_group import bands_worktree
from aiida_quantumespresso.worktrees.pdos_group import pdos_worktree

load_profile()

PwRelaxChainNode = build_node({'path': 'aiida_quantumespresso.workflows.pw.relax.PwRelaxWorkChain'})

atoms = bulk('Si')
structure_si = StructureData(ase=atoms)

pw_code = load_code('qe-7.2-pw@localhost')
dos_code = load_code('qe-7.2-dos@localhost')
projwfc_code = load_code('qe-7.2-projwfc@localhost')
paras = Dict({
    'CONTROL': {
        'calculation': 'scf',
    },
    'SYSTEM': {
        'ecutwfc': 40,
        'ecutrho': 300,
        'occupations': 'smearing',
        'smearing': 'gaussian',
        'degauss': 0.02,
    },
})
relax_paras = deepcopy(paras)
relax_paras.get_dict()['CONTROL']['calculation'] = 'relax'
bands_paras = deepcopy(paras)
bands_paras.get_dict()['CONTROL']['calculation'] = 'bands'
nscf_paras = deepcopy(paras)
nscf_paras.get_dict()['CONTROL']['calculation'] = 'nscf'

kpoints = KpointsData()
kpoints.set_kpoints_mesh([1, 1, 1])
# Load the pseudopotential family.
pseudo_family = load_group('SSSP/1.3/PBEsol/efficiency')
pseudos = pseudo_family.get_pseudos(structure=structure_si)
#
metadata = {
    'options': {
        'resources': {
            'num_machines': 1,
            'num_mpiprocs_per_machine': 2,
        },
    }
}

relax_inputs = {
    'base': {
        'pw': {
            'code': pw_code,
            'pseudos': pseudos,
            'parameters': relax_paras,
            'metadata': metadata,
        },
        'kpoints': kpoints,
    },
    'structure': structure_si,
}

bands_inputs = {
    'scf': {
        'pw': {
            'code': pw_code,
            'pseudos': pseudos,
            'parameters': paras,
            'metadata': metadata,
        },
        'kpoints': kpoints,
    },
    'bands': {
        'pw': {
            'code': pw_code,
            'pseudos': pseudos,
            'parameters': bands_paras,
            'metadata': metadata,
        },
        'kpoints': kpoints,
    },
}

pdos_inputs = {
    'scf': {
        'pw': {
            'code': pw_code,
            'pseudos': pseudos,
            'parameters': paras,
            'metadata': metadata,
        },
        'kpoints': kpoints,
    },
    'nscf': {
        'pw': {
            'code': pw_code,
            'pseudos': pseudos,
            'parameters': nscf_paras,
            'metadata': metadata,
        },
        'kpoints': kpoints,
    },
    'dos': {
        'code': dos_code,
        'metadata': metadata,
    },
    'projwfc': {
        'code': projwfc_code,
        'metadata': metadata,
    },
}

wt = WorkTree('Electronic Structure of Si')
relax_node = wt.nodes.new(PwRelaxChainNode, name='relax')
relax_node.set(relax_inputs)
bands_wt = bands_worktree(structure=structure_si, inputs=bands_inputs, run_relax=False)
pdos_wt = pdos_worktree(structure=structure_si, inputs=pdos_inputs, run_scf=True)
# append a wroktree
wt.append(bands_wt, prefix='bands_')
wt.append(pdos_wt, prefix='pdos_')
# adjust the links
wt.links.new(relax_node.outputs['output_structure'], wt.nodes['bands_scf'].inputs['pw.structure'])
wt.links.new(relax_node.outputs['output_structure'], wt.nodes['pdos_scf'].inputs['pw.structure'])
wt.run()
