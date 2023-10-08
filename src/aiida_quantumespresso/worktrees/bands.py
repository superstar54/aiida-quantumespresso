# -*- coding: utf-8 -*-
"""BandsWorkTree."""

from aiida import orm
from aiida.engine import calcfunction
from aiida_worktree import WorkTree, build_node
from aiida_worktree.decorator import node


@node()
@calcfunction
def generate_bands_parameters(parameters, output_parameters, nbands_factor=None):
    """Generate bands parameters from SCF calculation."""
    parameters = parameters.get_dict()
    parameters.setdefault('CONTROL', {})
    parameters.setdefault('SYSTEM', {})
    parameters.setdefault('ELECTRONS', {})
    if nbands_factor:
        factor = nbands_factor.value
        parameters = output_parameters.get_dict()
        nbands = int(parameters['number_of_bands'])
        nelectron = int(parameters['number_of_electrons'])
        nbnd = max(int(0.5 * nelectron * factor), int(0.5 * nelectron) + 4, nbands)
        parameters['SYSTEM']['nbnd'] = nbnd
    # Otherwise set the current number of bands, unless explicitly set in the inputs
    else:
        parameters['SYSTEM'].setdefault('nbnd', output_parameters.base.attributes.get('number_of_bands'))
    return orm.Dict(parameters)


def bands_worktree():
    """Generate BandsWorkTree."""
    # register node
    pw_node = build_node({'path': 'aiida_quantumespresso.workflows.pw.base.PwBaseWorkChain'})
    # create worktree
    tree = WorkTree('Bands')
    scf_node = tree.nodes.new(pw_node, name='scf')
    bands_node = tree.nodes.new(pw_node, name='bands')
    bands_parameters = tree.nodes.new(generate_bands_parameters, name='bands_parameters')
    tree.links.new(scf_node.outputs['remote_folder'], bands_node.inputs['pw.parent_folder'])
    tree.links.new(scf_node.outputs['output_parameters'], bands_parameters.inputs['output_parameters'])
    tree.links.new(bands_parameters.outputs[0], bands_node.inputs['pw.parameters'])
    # export worktree
    return tree
