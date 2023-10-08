# -*- coding: utf-8 -*-
"""PdosWorkTree."""

from aiida import orm
from aiida.engine import calcfunction
from aiida_worktree import WorkTree, build_node
from aiida_worktree.decorator import node


@node()
@calcfunction
def generate_dos_parameters(parameters, output_band, output_parameters):
    """Generate DOS parameters from NSCF calculation."""
    nscf_emin = output_band.get_array('bands').min()
    nscf_emax = output_band.get_array('bands').max()
    nscf_fermi = output_parameters.dict.fermi_energy
    paras = parameters.get_dict()
    paras.setdefault('DOS', {})
    if paras.pop('align_to_fermi', False):
        paras['DOS'].setdefault('Emax', nscf_emax)
        paras['DOS']['Emin'] = paras['DOS'].get('Emin', nscf_emin) + nscf_fermi
        paras['DOS']['Emax'] = paras['DOS'].get('Emin', nscf_emin) + nscf_fermi
    return orm.Dict(paras)


@node()
@calcfunction
def generate_projwfc_parameters(parameters, output_band, output_parameters):
    """Generate PROJWFC parameters from NSCF calculation."""
    nscf_emin = output_band.get_array('bands').min()
    nscf_emax = output_band.get_array('bands').max()
    nscf_fermi = output_parameters.dict.fermi_energy
    paras = parameters.get_dict()
    paras.setdefault('PROJWFC', {})
    if paras.pop('align_to_fermi', False):
        paras['PROJWFC']['Emin'] = paras['PROJWFC'].get('Emin', nscf_emin) + nscf_fermi
        paras['PROJWFC']['Emax'] = paras['PROJWFC'].get('Emax', nscf_emax) + nscf_fermi
    return orm.Dict(paras)


def pdos_worktree():
    """Generate PdosWorkTree."""
    # register node
    pw_node = build_node({'path': 'aiida_quantumespresso.workflows.pw.base.PwBaseWorkChain'})
    dos_node = build_node({'path': 'aiida_quantumespresso.calculations.dos.DosCalculation'})
    projwfc_node = build_node({'path': 'aiida_quantumespresso.calculations.projwfc.ProjwfcCalculation'})
    # create worktree
    tree = WorkTree('PDOS')
    scf_node = tree.nodes.new(pw_node, name='scf')
    nscf_node = tree.nodes.new(pw_node, name='nscf')
    tree.links.new(scf_node.outputs['remote_folder'], nscf_node.inputs['pw.parent_folder'])
    # dos
    dos_node = tree.nodes.new(dos_node, name='dos')
    dos_parameters = tree.nodes.new(generate_dos_parameters, name='dos_parameters')
    tree.links.new(nscf_node.outputs['remote_folder'], dos_node.inputs['parent_folder'])
    tree.links.new(nscf_node.outputs['output_band'], dos_parameters.inputs['output_band'])
    tree.links.new(nscf_node.outputs['output_parameters'], dos_parameters.inputs['output_parameters'])
    tree.links.new(dos_parameters.outputs[0], dos_node.inputs['parameters'])
    # projwfc
    projwfc_parameters = tree.nodes.new(generate_projwfc_parameters, name='projwfc_parameters')
    projwfc_node = tree.nodes.new(projwfc_node, name='projwfc')
    tree.links.new(nscf_node.outputs['remote_folder'], projwfc_node.inputs['parent_folder'])
    tree.links.new(nscf_node.outputs['output_band'], projwfc_parameters.inputs['output_band'])
    tree.links.new(nscf_node.outputs['output_parameters'], projwfc_parameters.inputs['output_parameters'])
    tree.links.new(projwfc_parameters.outputs[0], projwfc_node.inputs['parameters'])
    # export worktree
    return tree
