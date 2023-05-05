r"""Compilation of quantum circuits
===============================

Quantum circuits take many different forms from the moment we design them to the point where they
are ready to run in a quantum device. These changes happen during the compilation process of the
quantum circuits, which rely on the fact that there are many equivalent representations of quantum
circuits that use different sets of gates but provide the same output.

Out of those representations, we are typically interested in finding the most suitable one for our
purposes. For example, we usually look for the one that will incur the least amount of errors in the 
specific hardware for which we are compiling the circuit. This usually implies decomposing the
quantum gates in terms of the native ones of the quantum device, adapting the operations to the
hardrware's topology, combining them together to reduce the circuit depth, etc.

A great part of the compilation process consists on repeatedly performing minor circuit modifications.
In PennyLane, we can apply :mod:`~pennylane.transforms` to our quantum functions in order to obtain
equivalent ones that may be more convenient for our task. In this tutorial, we introduce the most
fundamental transforms involved in the compilation of quantum circuits.

Circuit transforms
==================

When we implement quantum algorithms, it is typically in our best interest that the resulting
circuits are as shallow as possible, especially with the noisy quantum devices available at present.
However, they often are more complex than needed containing multiple operations that could be
combined together to reduce the circuit complexity, although it is not always obvious. Here, we
introduce three simple circuit :mod:`~pennylane.transforms` that can be combined together to obtain
simpler quantum circuits. The transforms are based on very basic circuit equivalences:

.. figure:: qml/demonstrations/circuit_compilation/circuit_transforms.png
    :align: center
    :width: 90%

In order to illustrate their combined effect, let us consider the following circuit.
"""

import pennylane as qml

dev = qml.device("default.qubit", wires=3)


def circuit(angles):
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.RX(angles[0], 0)
    qml.CNOT(wires=[1, 0])
    qml.CNOT(wires=[2, 1])
    qml.RX(angles[2], wires=0)
    qml.RZ(angles[1], wires=2)
    qml.CNOT(wires=[2, 1])
    qml.RZ(-angles[1], wires=2)
    qml.CNOT(wires=[1, 0])
    qml.Hadamard(wires=1)
    qml.CY(wires=[1, 2])
    qml.CNOT(wires=[1, 0])
    return qml.expval(qml.PauliZ(wires=0))


angles = [0.1, 0.3, 0.5]
qnode = qml.QNode(circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# Given an arbitrary quantum circuit, it is usually hard to clearly understand what is really
# happening. To obtain a better picture, we can shuffle the commuting operations to better distinguish
# between groups of single-qubit and two-qubit gates. We can easily do so by applying the
# :func:`~pennylane.transforms.commute_controlled` transform.
#

commuted_circuit = qml.transforms.commute_controlled()(circuit)

qnode = qml.QNode(commuted_circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# With this rearrangement, we can clearly identify a few operations that can be merged together.
# First, the two consecutive CNOT gates from the third to the second qubits will cancel each other
# out. We can remove these with the :func:`~pennylane.transforms.cancel_inverses`
# transform, which removes consecutive inverse operations. Then, we can combine the two :class:`~.RX`
# rotations in the first qubit into a single one with the sum of the angles. Finally, the two :class:`~.RZ`
# rotations in the third qubit will also cancel each other. We can combine these rotations with the
# :func:`~pennylane.transforms.merge_rotations` transform.
#
# Let us see the result of applying both transforms to the rearranged circuit. We start with the
# ``cancel_inverses`` one.
#

cancelled_circuit = qml.transforms.cancel_inverses(commuted_circuit)


qnode = qml.QNode(cancelled_circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# Now we combine the rotations together.
#

merged_circuit = qml.transforms.merge_rotations()(cancelled_circuit)


qnode = qml.QNode(merged_circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# Combining these simple circuit transforms, we have reduced the complexity of our original circuit.
# This will make it faster to execute and less prone to errors.
#
# We can directly apply the transforms to our quantum function when we define it using their decorator
# forms (beware the reverse order!).
#


@qml.qnode(dev)
@qml.transforms.merge_rotations()
@qml.transforms.cancel_inverses
@qml.transforms.commute_controlled()
def q_fun(angles):
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.RX(angles[0], 0)
    qml.CNOT(wires=[1, 0])
    qml.CNOT(wires=[2, 1])
    qml.RX(angles[2], wires=0)
    qml.RZ(angles[1], wires=2)
    qml.CNOT(wires=[2, 1])
    qml.RZ(-angles[1], wires=2)
    qml.CNOT(wires=[1, 0])
    qml.Hadamard(wires=1)
    qml.CY(wires=[1, 2])
    qml.CNOT(wires=[1, 0])
    return qml.expval(qml.PauliZ(wires=0))


qml.draw_mpl(q_fun, decimals=1)(angles)

######################################################################
# Circuit compilation
# ===================
#
# Rearranging and combining operations is an essential part of circuit compilation. Indeed, it is
# usually performed repeatedly as the compiler does multiple *passess* over the circuit. At every
# pass, the compiler applies a series of circuit transforms to obtain better and better circuit
# representations.
#
# We can apply all the transforms introduced above with the
# :func:`~pennylane.transforms.compile` function, which yields the same final circuit.
#

compiled_circuit = qml.compile()(circuit)

qnode = qml.QNode(compiled_circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# In the resulting circuit, we can identify further operations that can be combined, such as the
# consecutive CNOT gates applied from the second to the first qubit. To do so, we would simply need to
# apply the same transforms again in a second pass of the compiler. We can adjust the desired number
# of passes with ``num_passes``.
#
# Let us see the resulting circuit with two passes.
#

compiled_circuit = qml.compile(num_passes=2)(circuit)

qnode = qml.QNode(compiled_circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# This can be further simplified with an additional pass of the compiler. In this case, we also define
# explicitly the transforms to be applied by the compiler with the ``pipeline`` argument. This allows
# us to control the transforms, their parameters, and the order in which they are applied.
#

compiled_circuit = qml.compile(
    pipeline=[
        qml.transforms.commute_controlled(direction="left"),
        qml.transforms.merge_rotations(atol=1e-6),
        qml.transforms.cancel_inverses,  # Cancel inverses after rotations
    ],
    num_passes=3,
)(circuit)

qnode = qml.QNode(compiled_circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# Notice how the :class:`~.RX` gate in the first qubit has now been pushed towards the left (it defaults to
# the right), as we have specified in the ``commute_controlled`` transform.
#
# Finally, we can specify a finite basis of gates to describe the circuit providing a ``basis_set``.
# For example, we can choose to only use single-qubit rotations and CNOT operations. The compiler will
# first decompose the gates in terms of our basis and, then, apply the transforms.
#

compiled_circuit = qml.compile(basis_set=["CNOT", "RX", "RY", "RZ"], num_passes=2)(circuit)

qnode = qml.QNode(compiled_circuit, dev)
qml.draw_mpl(qnode, decimals=1)(angles)

######################################################################
# We can see how the Hadamard and control Y gates have been decomposed into a series of single-qubit
# rotations and CNOT gates.
#
# In this tutorial, we have learned the basic principles of the compilation of quantum circuits.
# Combining simple circuit transforms that are applied repeatedly in passes of the compiler, we can
# significantly reduce the complexity of our quantum circuits.
#
