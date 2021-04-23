import netsquid as ns
import netsquid.components.instructions as instr
import numpy as np
from netsquid.components import QuantumProgram, SourceStatus
from netsquid.protocols import NodeProtocol, Signals

from qkd.networks import TwoPartyNetwork


class KeyReceiverProtocol(NodeProtocol):
    """
    Protocol for the receiver of the key.
    """

    def __init__(self, node, key_size=10, port_names=("qubitIO", "classicIO")):
        super().__init__(node)
        self.node = node
        self.q_port = port_names[0]
        self.c_port = port_names[1]
        self.key_size = key_size
        self.key = None

    def run(self):
        # Select random bases
        bases = np.random.randint(2, size=self.key_size)
        results = []
        qubits_received = 0

        def record_measurement(msg):
            results.append(msg.items[0])

        def measure_qubit(message):
            nonlocal qubits_received
            if bases[qubits_received] == 0:
                self.node.qmemory.subcomponents['qubit_detector_z'].ports['qin0'].tx_input(message)
            else:
                self.node.qmemory.subcomponents['qubit_detector_x'].ports['qin0'].tx_input(message)
            qubits_received += 1

        self.node.ports[self.q_port].bind_input_handler(measure_qubit)
        self.node.qmemory.subcomponents['qubit_detector_z'].ports['cout0'].bind_output_handler(record_measurement)
        self.node.qmemory.subcomponents['qubit_detector_x'].ports['cout0'].bind_output_handler(record_measurement)

        # Await done signal from Alice
        yield self.await_port_input(self.node.ports[self.c_port])

        # All qubits sent, send bases back
        self.node.ports[self.c_port].tx_output(bases[:len(results)])

        # Await matched indices from Alice and process key
        yield self.await_port_input(self.node.ports[self.c_port])
        matched_indices = self.node.ports[self.c_port].rx_input().items
        final_key = []

        for i in matched_indices:
            if i < len(results):
                final_key.append(results[i])

        self.key = final_key
        self.send_signal(signal_label=Signals.SUCCESS, result=final_key)


class KeySenderProtocol(NodeProtocol):
    """
    Protocol for the sender of the key.
    """

    def __init__(self, node, key_size=10, port_names=("qubitIO", "classicIO")):
        super().__init__(node)
        self.node = node
        self.q_port = port_names[0]
        self.c_port = port_names[1]
        self.key_size = key_size
        self.key = None

    def run(self):
        bases = list(np.random.randint(2, size=self.key_size))
        bit = 0
        results = []

        # Transmit encoded qubits to Bob
        def record_measurement(msg):
            results.append(msg.items[0])

        def measure_half(message):
            nonlocal bit
            if bases[bit] == 0:
                self.node.qmemory.subcomponents['qubit_detector_z'].ports['qin0'].tx_input(message)
            else:
                self.node.qmemory.subcomponents['qubit_detector_x'].ports['qin0'].tx_input(message)

        self.node.qmemory.subcomponents['ent_source'].ports['qout0'].bind_output_handler(measure_half)
        self.node.qmemory.subcomponents['qubit_detector_z'].ports['cout0'].bind_output_handler(record_measurement)
        self.node.qmemory.subcomponents['qubit_detector_x'].ports['cout0'].bind_output_handler(record_measurement)

        self.node.qmemory.subcomponents['ent_source'].status = SourceStatus.INTERNAL
        for i in range(self.key_size):
            yield self.await_port_output(self.node.qmemory.subcomponents['ent_source'].ports['qout1'])
            self.node.ports[self.q_port].tx_output(
                self.node.qmemory.subcomponents['ent_source'].ports['qout1'].rx_output())

        self.node.qmemory.subcomponents['ent_source'].status = SourceStatus.OFF
        self.node.ports[self.c_port].tx_output('DONE')

        # Await response from Bob
        yield self.await_port_input(self.node.ports[self.c_port])
        bob_bases = self.node.ports[self.c_port].rx_input().items[0]
        matched_indices = []
        for i in range(self.key_size):
            if bob_bases[i] == bases[i]:
                matched_indices.append(i)
        self.node.ports[self.c_port].tx_output(matched_indices)
        final_key = []
        for i in matched_indices:
            final_key.append(results[i])
        self.key = final_key
        self.send_signal(signal_label=Signals.SUCCESS, result=final_key)


if __name__ == '__main__':
    n = TwoPartyNetwork('net', 0, 0, 10, t_time={'T1': 110, 'T2': 100}, loss=(0, 0)).generate_noisy_network()
    node_a = n.get_node("alice")
    node_b = n.get_node("bob")

    p1 = KeySenderProtocol(node_a, key_size=100)
    p2 = KeyReceiverProtocol(node_b, key_size=100)

    p1.start()
    p2.start()

    # ns.logger.setLevel(4)

    stats = ns.sim_run()

    print(len(p1.key))
    print(p1.key)
    print(p2.key)
