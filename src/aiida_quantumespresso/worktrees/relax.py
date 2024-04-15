# -*- coding: utf-8 -*-
"""PdosWorkTree."""

from aiida import orm
from aiida_worktree import WorkTree, build_node
from aiida_worktree.decorator import node

# register node
PwBaseNode = build_node({'path': 'aiida_quantumespresso.workflows.pw.base.PwBaseWorkChain'})


@node()
def inspect_relax(outputs, prev_cell_volume, volume_threshold=0.1):
    """Inspect relax calculation."""
    structure = outputs.output_structure
    curr_cell_volume = structure.get_cell_volume()
    current_number_of_bands = outputs.output_parameters.get_dict()['number_of_bands']
    volume_difference = abs(prev_cell_volume - curr_cell_volume) / prev_cell_volume
    if volume_difference < volume_threshold:
        is_converged = True

    return {
        'prev_cell_volume': curr_cell_volume,
        'current_number_of_bands': orm.Int(current_number_of_bands),
        'is_converged': orm.Bool(is_converged)
    }


@node.group()
def relax_worktree(structure, inputs, max_iterations=5, volume_threshold=0.1, run_final_scf=True):
    """Generate PdosWorkTree."""
    # create worktree
    tree = WorkTree()
    tree.worktree_type = 'WHILE'
    tree.max_iterations = max_iterations
    tree.conditions = []
    tree.ctx = {
        'current_structure': structure,
        'current_number_of_bands': None,
        'current_cell_volume': None,
        'is_converged': False,
        'iteration': 0,
    }
    # -------- relax -----------
    relax_node = tree.nodes.new(PwBaseNode, name='relax')
    relax_inputs = inputs.get('relax', {})
    relax_inputs['pw.structure'] = structure
    relax_node.set(relax_inputs)
    relax_node.to_ctx = [['output_structure', 'current_structure']]
    # -------- inspect relax -----------
    inspect_relax_node = tree.nodes.new(inspect_relax, name='inspect_relax', volume_threshold=volume_threshold)
    tree.links.new(relax_node.outputs['_outputs'], inspect_relax_node.inputs['outputs'])
    inspect_relax_node.to_ctx = [['current_number_of_bands', 'current_number_of_bands'],
                                 ['current_structure', 'current_structure'],
                                 ['current_cell_volume', 'prev_cell_volume'], ['is_converged', 'is_converged']]
    # -------- scf -----------
    scf_node = tree.nodes.new(PwBaseNode, name='scf')
    scf_inputs = inputs.get('scf', {})
    scf_inputs['pw.structure'] = structure
    scf_node.set(scf_inputs)
    scf_node.to_ctx = [['output_structure', 'current_structure']]
    if not run_final_scf:
        tree.nodes.delete('scf')
    # export worktree
    return tree
