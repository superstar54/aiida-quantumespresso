# -*- coding: utf-8 -*-
"""BandsWorkTree."""

from aiida import orm
from aiida.engine import calcfunction
from aiida_worktree import WorkTree, build_node
from aiida_worktree.decorator import node

# register node
PwBaseChainNode = build_node({'path': 'aiida_quantumespresso.workflows.pw.base.PwBaseWorkChain'})
PwRelaxChainNode = build_node({'path': 'aiida_quantumespresso.workflows.pw.relax.PwRelaxWorkChain'})
SeekpathNode = build_node({
    'path':
    'aiida_quantumespresso.calculations.functions.seekpath_structure_analysis.seekpath_structure_analysis'
})


@node()
@calcfunction
def inspect_relax(output_parameters):
    """Inspect relax calculation."""
    current_number_of_bands = output_parameters.base.attributes.get('number_of_bands')
    return {'current_number_of_bands': orm.Int(current_number_of_bands)}


@node()
@calcfunction
def generate_scf_parameters(parameters, current_number_of_bands):
    """Generate scf parameters from relax calculation."""
    parameters = parameters.get_dict()
    parameters.setdefault('SYSTEM', {})
    parameters['SYSTEM'].setdefault('nbnd', current_number_of_bands)
    return orm.Dict(parameters)


@node()
@calcfunction
def inspect_scf(output_parameters):
    """Inspect scf calculation."""
    current_number_of_bands = output_parameters.base.attributes.get('number_of_bands')
    return {'current_number_of_bands': orm.Int(current_number_of_bands)}


@node()
@calcfunction
def generate_bands_parameters(parameters, output_parameters, nbands_factor=None):
    """Generate bands parameters from SCF calculation."""
    parameters = parameters.get_dict()
    parameters.setdefault('SYSTEM', {})
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


@node.group()
def bands_worktree(structure, inputs, run_relax=False, bands_kpoints_distance=None, nbands_factor=None):
    """BandsWorkTree."""
    # create worktree
    tree = WorkTree('Bands')
    tree.ctx = {'current_structure': structure, 'current_number_of_bands': None, 'bands_kpoints': None}
    #
    scf_node = tree.nodes.new(PwBaseChainNode, name='scf')
    scf_inputs = inputs.get('scf')
    scf_inputs['pw.structure'] = '{{current_structure}}'
    scf_node.set(scf_inputs)
    scf_parameters = tree.nodes.new(
        generate_scf_parameters,
        name='scf_parameters',
        parameters=scf_inputs['pw']['parameters'],
        current_number_of_bands='{{current_number_of_bands}}'
    )
    tree.links.new(scf_parameters.outputs[0], scf_node.inputs['pw.parameters'])
    inspect_scf_node = tree.nodes.new(inspect_scf, name='inspect_scf')
    tree.links.new(scf_node.outputs['output_parameters'], inspect_scf_node.inputs['output_parameters'])
    #
    bands_node = tree.nodes.new(PwBaseChainNode, name='bands')
    bands_inputs = inputs.get('bands')
    bands_inputs['pw.structure'] = '{{current_structure}}'
    bands_node.set(bands_inputs)
    bands_parameters = tree.nodes.new(
        generate_bands_parameters,
        name='bands_parameters',
        parameters=bands_inputs['pw']['parameters'],
        nbands_factor=nbands_factor,
    )
    tree.links.new(scf_node.outputs['remote_folder'], bands_node.inputs['pw.parent_folder'])
    tree.links.new(scf_node.outputs['output_parameters'], bands_parameters.inputs['output_parameters'])
    tree.links.new(bands_parameters.outputs[0], bands_node.inputs['pw.parameters'])
    if run_relax:
        relax_node = tree.nodes.new(PwRelaxChainNode, name='relax')
        relax_inputs = inputs.get('relax')
        relax_inputs['structure'] = '{{current_structure}}'
        relax_node.set(relax_inputs)
        relax_node.to_ctx = [['output_structure', 'current_structure']]
        inspect_relax_node = tree.nodes.new(inspect_relax, name='inspect_relax')
        inspect_relax_node.to_ctx = [['current_number_of_bands', 'current_number_of_bands']]
        tree.links.new(relax_node.outputs['output_parameters'], inspect_relax_node.inputs['output_parameters'])
        scf_parameters.wait.append('inspect_relax')
    if bands_kpoints_distance is not None:
        seekpath_node = tree.nodes.new(
            SeekpathNode,
            name='seekpath',
            structure='{{current_structure}}',
            kwargs={'reference_distance': bands_kpoints_distance}
        )
        seekpath_node.to_ctx = [['primitive_structure', 'current_structure'], ['explicit_kpoints', 'bands_kpoints']]
        scf_parameters.wait.append('seekpath')
        if run_relax:
            seekpath_node.wait = ['inspect_relax']
    # export worktree
    return tree
