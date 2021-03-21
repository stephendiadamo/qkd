import netsquid as ns
import netsquid.components.instructions as instr
from netsquid.components import QuantumChannel, QuantumProgram, ClassicalChannel, FibreDelayModel, DephaseNoiseModel, \
    T1T2NoiseModel, QSource, SourceStatus, FibreLossModel
from netsquid.components.qprocessor import QuantumProcessor, PhysicalInstruction
from netsquid.nodes import Node, Network, Connection
from netsquid.qubits import StateSampler
import netsquid.qubits.ketstates as ks


class Network():

    def __init__(self, length, dephase_rate, memory_size, t_time, q_source_probs, loss):
        self._length = length
        self._dephase_rate = dephase_rate
        self._memory_size = memory_size
        self._t_time = t_time
        self._q_source_probs = q_source_probs
        self._loss = loss

    def _create_processor(self, dephase_rate, t_times, memory_size,
                          add_qsource=False, q_source_probs=[1., 0.]):
        """Factory to create a quantum processor for each end node.

        Has three memory positions and the physical instructions necessary
        for teleportation.
        """

        gate_noise_model = DephaseNoiseModel(dephase_rate, time_independent=False)
        memory_noise_model = T1T2NoiseModel(T1=t_times['T1'], T2=t_times['T2'])

        physical_instructions = [
            PhysicalInstruction(instr.INSTR_INIT,
                                duration=1,
                                parallel=False,
                                q_noise_model=gate_noise_model),
            PhysicalInstruction(instr.INSTR_H,
                                duration=1,
                                parallel=False,
                                q_noise_model=gate_noise_model),
            PhysicalInstruction(instr.INSTR_X,
                                duration=1,
                                parallel=False,
                                q_noise_model=gate_noise_model),
            PhysicalInstruction(instr.INSTR_Z,
                                duration=1,
                                parallel=False,
                                q_noise_model=gate_noise_model),
            PhysicalInstruction(instr.INSTR_MEASURE,
                                duration=10,
                                parallel=False,
                                q_noise_model=gate_noise_model),
            PhysicalInstruction(instr.INSTR_MEASURE_X,
                                duration=10,
                                parallel=False,
                                q_noise_model=gate_noise_model)
        ]
        processor = QuantumProcessor("quantum_processor",
                                     num_positions=memory_size,
                                     mem_noise_models=[memory_noise_model] * memory_size,
                                     phys_instructions=physical_instructions)
        if add_qsource:
            qubit_source = QSource('qubit_source',
                                   StateSampler([ks.s0, ks.s1], q_source_probs),
                                   num_ports=1,
                                   status=SourceStatus.OFF)
            processor.add_subcomponent(qubit_source,
                                       name='qubit_source')
        return processor

    class QubitConnection(Connection):

        def __init__(self, length, dephase_rate, loss=(0, 0), name='QubitConn'):
            super().__init__(name=name)
            error_models = {'quantum_noise_model': DephaseNoiseModel(dephase_rate=dephase_rate,
                                                                     time_independent=False),
                            'delay_model': FibreDelayModel(length=length),
                            'quantum_loss_model': FibreLossModel(p_loss_init=loss[0], p_loss_length=loss[1])
                            }
            q_channel = QuantumChannel(name='q_channel',
                                       length=length,
                                       models=error_models
                                       )
            self.add_subcomponent(q_channel,
                                  forward_output=[('B', 'recv')],
                                  forward_input=[('A', 'send')])

    def generate_network():
        """
        Generate the QKD network.
        """
        if self._t_time is None:
            self._t_time = {'T1': 11, 'T2': 10}

        network = Network("Noisy Network")
        alice = Node(
            "alice",
            qmemory=self._create_processor(self._dephase_rate,
                                           self._t_time,
                                           self._memory_size,
                                           add_qsource=True,
                                           q_source_probs=self._q_source_probs))
        bob = Node(
            "bob",
            qmemory=self._create_processor(
                self._dephase_rate,
                self._t_time,
                self._memory_size))
        network.add_nodes([alice, bob])
        q_conn = QubitConnection(
            length=self._length,
            dephase_rate=self._dephase_rate,
            loss=self._loss)
        network.add_connection(alice,
                               bob,
                               label='q_chan',
                               connection=q_conn,
                               port_name_node1='qubitIO',
                               port_name_node2='qubitIO')
        network.add_connection(alice,
                               bob,
                               label="c_chan",
                               channel_to=ClassicalChannel('AcB', delay=10),
                               channel_from=ClassicalChannel('BcA', delay=10),
                               port_name_node1="classicIO",
                               port_name_node2="classicIO")
        return network
