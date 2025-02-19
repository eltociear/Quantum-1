# !/usr/bin/env python3
# Copyright (c) 2022 Institute for Quantum Computing, Baidu Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r"""
The source file of the class for the special quantum operator.
"""

import numpy as np
import paddle

import warnings
import paddle_quantum as pq
from ..base import Operator
from ..backend import Backend
from ..backend import state_vector, density_matrix, unitary_matrix
from ..intrinsic import _format_qubits_idx, _get_float_dtype
from ..state import State
from ..qinfo import partial_trace_discontiguous
from typing import Union, Iterable


class ResetState(Operator):
    r"""The class to reset the quantum state. It will be implemented soon.
    """
    def __init__(self):
        super().__init__()

    def forward(self, *inputs, **kwargs):
        r"""The forward function.

        Returns:
            NotImplemented.
        """
        return NotImplemented


class PartialState(Operator):
    r"""The class to obtain the partial quantum state. It will be implemented soon.
    """
    def __init__(self):
        super().__init__()

    def forward(self, *inputs, **kwargs):
        r"""The forward function.

        Returns:
            NotImplemented.
        """
        return NotImplemented


class Collapse(Operator):
    r"""The class to compute the collapse of the quantum state.

    Args:
        qubits_idx: list of qubits to be collapsed. Defaults to ``'full'``.
        num_qubits: Total number of qubits. Defaults to ``None``.
        desired_result: The desired result you want to collapse. Defaults to ``None`` meaning randomly choose one.
        if_print: whether print the information about the collapsed state. Defaults to ``False``.
        measure_basis: The basis of the measurement. The quantum state will collapse to the corresponding eigenstate.

    Raises:
        NotImplementedError: If the basis of measurement is not z. Other bases will be implemented in future.
        
    Note:
        When desired_result is `None`, Collapse does not support gradient calculation
    """
    def __init__(self, qubits_idx: Union[Iterable[int], int, str] = 'full', num_qubits: int = None,
                 desired_result: Union[int, str] = None, if_print: bool = False,
                 measure_basis: Union[Iterable[paddle.Tensor], str] = 'z'):
        super().__init__()
        self.measure_basis = []

        # the qubit indices must be sorted
        self.qubits_idx = sorted(_format_qubits_idx(qubits_idx, num_qubits))

        self.desired_result = desired_result
        self.if_print = if_print

        if measure_basis in ['z', 'computational_basis']:
            self.measure_basis = 'z'
        else:
            raise NotImplementedError
        
    def forward(self, state: State) -> State:
        r"""Compute the collapse of the input state.

        Args:
            state: The input state, which will be collapsed

        Returns:
            The collapsed quantum state.
        """
        complex_dtype = pq.get_dtype()
        float_dtype = _get_float_dtype(complex_dtype)    

        backend = state.backend
        num_acted_qubits = len(self.qubits_idx)
        desired_result = self.desired_result
        desired_result = int(desired_result, 2) if isinstance(desired_result, str) else desired_result 
        
        def projector_gen() -> paddle.Tensor:
            proj = paddle.zeros([2 ** num_acted_qubits, 2 ** num_acted_qubits])
            proj[desired_result, desired_result] += 1
            proj = proj.cast(complex_dtype)
            return proj
        
        num_qubits = state.num_qubits
        # when backend is unitary
        if backend == Backend.UnitaryMatrix:
            assert isinstance(desired_result, int), "desired_result cannot be None in unitary_matrix backend"
            warnings.warn(
                "the unitary_matrix of a circuit containing Collapse operator is no longer a unitary"
            )

            local_projector = projector_gen()

            projected_state = unitary_matrix.unitary_transformation(state.data, local_projector, self.qubits_idx, num_qubits)
            return State(projected_state, backend=Backend.UnitaryMatrix)

        # retrieve prob_amplitude
        rho = state.ket @ state.bra if backend == Backend.StateVector else state.data
        rho = partial_trace_discontiguous(rho, self.qubits_idx)
        prob_amplitude = paddle.zeros([2 ** num_acted_qubits], dtype=float_dtype)
        for idx in range(2 ** num_acted_qubits):
            prob_amplitude[idx] += rho[idx, idx].real()
        prob_amplitude /= paddle.sum(prob_amplitude)

        if desired_result is None:
            # randomly choose desired_result
            desired_result = np.random.choice(list(range(2**num_acted_qubits)), p=prob_amplitude)

        else:
            desired_result_str = bin(desired_result)[2:]
            # check whether the state can collapse to desired_result
            assert prob_amplitude[desired_result] > 1e-20, \
                f"it is infeasible for the state in qubits {self.qubits_idx} to collapse to state |{bin(desired_result)[2:]}>"


        # retrieve the binary version of desired result
        desired_result_str = bin(desired_result)[2:]
        assert num_acted_qubits >= len(desired_result_str), "the desired_result is too large"
        for _ in range(num_acted_qubits - len(desired_result_str)):
            desired_result_str = f'0{desired_result_str}'

        # whether print the collapsed result
        if self.if_print:
            # retrieve binary representation
            prob = prob_amplitude[desired_result].item()
            print(f"qubits {self.qubits_idx} collapse to the state |{desired_result_str}> with probability {prob}")

        local_projector = projector_gen()

        # apply the local projector and normalize it
        if backend == Backend.StateVector:
            projected_state = state_vector.unitary_transformation(state.data, local_projector, self.qubits_idx, num_qubits)
        else:
            projected_state = density_matrix.unitary_transformation(state.data, local_projector, self.qubits_idx, num_qubits)
        state = State(projected_state)
        state.normalize()
        return state
