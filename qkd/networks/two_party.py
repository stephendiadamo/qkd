import netsquid.components.instructions as instr
import netsquid.qubits.ketstates as ks

from netsquid.components import QuantumChannel, ClassicalChannel, FibreDelayModel, DephaseNoiseModel, \
    T1T2NoiseModel, QSource, SourceStatus, FibreLossModel, QuantumDetector
from netsquid.components.qprocessor import QuantumProcessor, PhysicalInstruction
from netsquid.nodes import Node, Network, Connection
from netsquid.qubits import StateSampler, operators as ops


class QubitConnection(Connection):

    def __init__(self, length, dephase_rate, loss=(0, 0), name='QubitConn'):
        super().__init__(name=name)
        error_models = {'quantum_noise_model': DephaseNoiseModel(dephase_rate=dephase_rate,
                                                                 time_independent=False),
                        'delay_model': FibreDelayModel(length=length),
                        'quantum_loss_model': FibreLossModel(p_loss_init=loss[0],
                                                             p_loss_length=loss[1])
                        }
        q_channel = QuantumChannel(name='q_channel', length=length, models=error_models)
        self.add_subcomponent(q_channel, forward_output=[('B', 'recv')], forward_input=[('A', 'send')])


class TwoPartyNetwork:

    def __init__(self, name='network', length=0, dephase_rate=0, memory_size=100, t_time=None, q_source_probs=(1., 0.),
                 loss=(0, 0)):
        self.name = name
        self._length = length
        self._dephase_rate = dephase_rate
        self._memory_size = memory_size
        if t_time is None:
            self._t_time = {'T1': 11, 'T2': 10}
        else:
            self._t_time = t_time
        self._q_source_probs = q_source_probs
        self._loss = loss

    @staticmethod
    def _create_noiseless_processor(with_ent_source=False):
        """Factory to create a quantum processor for each end node.

        Has three memory positions and the physical instructions necessary
        for teleportation.
        """
        physical_instructions = [
            PhysicalInstruction(instr.INSTR_INIT, duration=3, parallel=True),
            PhysicalInstruction(instr.INSTR_H, duration=1, parallel=True),
            PhysicalInstruction(instr.INSTR_X, duration=1, parallel=True),
            PhysicalInstruction(instr.INSTR_Z, duration=1, parallel=True),
            PhysicalInstruction(instr.INSTR_MEASURE, duration=7, parallel=False),
            PhysicalInstruction(instr.INSTR_MEASURE_X, duration=10, parallel=False)
        ]
        processor = QuantumProcessor("quantum_processor",
                                     phys_instructions=physical_instructions)

        if with_ent_source:
            ent_source = QSource('ent_source',
                                 StateSampler([ks.b00]),
                                 num_ports=2,
                                 status=SourceStatus.OFF)
            processor.add_subcomponent(ent_source,
                                       name='ent_source')

        return processor

    @staticmethod
    def _create_processor(dephase_rate, t_times, memory_size, qsource=None, qdetect=None):

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
        if qsource is not None:
            qubit_source = QSource('qubit_source',
                                   StateSampler([ks.s0, ks.s1], list(qsource['probs'])),
                                   double_frequency=qsource['freq'],
                                   num_ports=1,
                                   status=SourceStatus.OFF)
            processor.add_subcomponent(qubit_source)

        if qdetect is not None:
            qubit_detector_z = QuantumDetector('qubit_detector_z',
                                               system_delay=qdetect['sys_delay'],
                                               dead_time=qdetect['dead_time'])
            qubit_detector_x = QuantumDetector('qubit_detector_x',
                                               system_delay=qdetect['sys_delay'],
                                               dead_time=qdetect['dead_time'],
                                               observable=ops.X)
            processor.add_subcomponent(qubit_detector_z)
            processor.add_subcomponent(qubit_detector_x)

        return processor

    @staticmethod
    def _generate_network(name, with_ent=False):
        network = Network(name)
        alice = Node("alice", qmemory=TwoPartyNetwork._create_noiseless_processor(with_ent))
        bob = Node("bob", qmemory=TwoPartyNetwork._create_noiseless_processor())

        network.add_nodes([alice, bob])
        p_ab, p_ba = network.add_connection(alice,
                                            bob,
                                            label="q_chan",
                                            channel_to=QuantumChannel('AqB', delay=10),
                                            channel_from=QuantumChannel('BqA', delay=10),
                                            port_name_node1="qubitIO",
                                            port_name_node2="qubitIO")

        alice.ports[p_ab].forward_input(alice.qmemory.ports["qin0"])
        bob.ports[p_ba].forward_input(bob.qmemory.ports["qin0"])
        network.add_connection(alice,
                               bob,
                               label="c_chan",
                               channel_to=ClassicalChannel('AcB', delay=10),
                               channel_from=ClassicalChannel('BcA', delay=10),
                               port_name_node1="classicIO",
                               port_name_node2="classicIO")
        return network

    def generate_noiseless_network(self):
        return TwoPartyNetwork._generate_network(self.name)

    def generate_noiseless_ent_network(self):
        return TwoPartyNetwork._generate_network(self.name, True)

    def generate_noisy_network(self):
        """
        Generate the QKD network.
        """

        network = Network("Noisy Network")
        alice = Node(
            "alice",
            qmemory=self._create_processor(
                self._dephase_rate,
                self._t_time,
                self._memory_size,
                qsource={
                    'freq': 1,
                    'probs': self._q_source_probs
                }
            )
        )
        bob = Node(
            "bob",
            qmemory=self._create_processor(
                self._dephase_rate,
                self._t_time,
                self._memory_size,
                qdetect={'sys_delay': 0, 'dead_time': 0}))
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
