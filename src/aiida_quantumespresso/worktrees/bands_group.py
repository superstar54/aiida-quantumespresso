# -*- coding: utf-8 -*-
"""BandsWorkTree."""

from aiida import orm
from aiida.engine import calcfunction
from aiida_worktree import WorkTree, build_node
from aiida_worktree.decorator import node

# register node
pw_base_chain = build_node({'path': 'aiida_quantumespresso.workflows.pw.base.PwBaseWorkChain'})
pw_relax_chain = build_node({'path': 'aiida_quantumespresso.workflows.pw.base.PwRelaxWorkChain'})
seekpath_calc = build_node({'path': 'aiida_quantumespresso.calculations.functions.seekpath_structure_analysis.seekpath_structure_analysis'})


@node()
@calcfunction
def inspect_relax(output_structure, output_parameters):
    current_structure = output_structure
    current_number_of_bands = output_parameters.base.attributes.get('number_of_bands')
    return {"current_structure": current_structure,
            "current_number_of_bands": current_number_of_bands}

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
    current_number_of_bands = output_parameters.base.attributes.get('number_of_bands')
    return {"current_number_of_bands": current_number_of_bands}

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
def bands_worktree(structure, inputs, run_relax=False, bands_kpoints_distance=None):
    # create worktree
    tree = WorkTree('Bands')
    tree.ctx = {"current_structure": structure,
                "current_number_of_bands": None,
                "bands_kpoints": None}
    #
    scf_node = tree.nodes.new(pw_base_chain, name='scf',
                              structure="{{current_structure}}")
    scf_node.set(inputs.get("scf"))
    scf_parameters = tree.nodes.new(generate_scf_parameters,
                                    name='scf_parameters',
                                    current_number_of_bands="{{current_number_of_bands}}")
    tree.links.new(scf_parameters.outputs[0], scf_node.inputs['pw.parameters'])
    inspect_scf_node = tree.nodes.new(inspect_scf, name='inspect_scf')
    tree.links(scf_node.outputs["output_parameters"],
                    inspect_scf_node.inputs["output_parameters"])
    #
    bands_node = tree.nodes.new(pw_base_chain, name='bands',
                                bands_kpoints="{{bands_kpoints}}")
    bands_node.set(inputs.get("bands"))
    bands_parameters = tree.nodes.new(generate_bands_parameters, name='bands_parameters')
    tree.links.new(scf_node.outputs['remote_folder'], bands_node.inputs['pw.parent_folder'])
    tree.links.new(scf_node.outputs['output_parameters'], bands_parameters.inputs['output_parameters'])
    tree.links.new(bands_parameters.outputs[0], bands_node.inputs['pw.parameters'])
    if bands_kpoints_distance is not None:
        seekpath_node = tree.nodes.new(seekpath_calc,
                                       name='seekpath',
                                       structure="{{current_structure}}",
                                       reference_distance=bands_kpoints_distance)
        seekpath_node.to_ctx = [["primitive_structure", "current_structure"],
                                ["explicit_kpoints", "bands_kpoints"]]
        scf_node.wait.append("seekpath")
        if run_relax:
            seekpath_node.wait = ["inspect_relax"]
    if run_relax:
        relax_node = tree.nodes.new(pw_relax_chain, name='relax')
        relax_node.set(inputs.get("relax"))
        inspect_relax_node = tree.nodes.new(inspect_relax, name='inspect_relax')
        tree.links(relax_node.outputs["output_structure"],
                    inspect_relax_node.inputs["output_structure"])
        tree.links(relax_node.outputs["output_parameters"],
                    inspect_relax_node.inputs["output_parameters"])
        scf_node.wait.append("inspect_relax")
    # export worktree
    return tree
