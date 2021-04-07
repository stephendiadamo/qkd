import time

import netsquid as ns
import netsquid.components.instructions as instr
import numpy as np
from netsquid.components import QuantumProgram, SourceStatus
from netsquid.protocols import NodeProtocol, Signals

from qkd.networks import TwoPartyNetwork

bob_keys = []
alice_keys = []


class EncodeQubitProgram(QuantumProgram):
    """
    Program to encode a bit according to a secret key and a basis.
    """

    def __init__(self, base, bit):
        super().__init__()
        self.base = base
        self.bit = bit

    def program(self):
        q1, = self.get_qubit_indices(1)
        if self.bit == 1:
            self.apply(instr.INSTR_X, q1)
        if self.base == 1:
            self.apply(instr.INSTR_H, q1)
        yield self.run()


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

        self.node.ports[self.q_port].forward_input(self.node.qmemory.ports["qin0"])
        self.node.qmemory.ports["qin0"].bind_input_handler(measure_qubit)
        self.node.qmemory.subcomponents['qubit_detector_z'].ports['cout0'].bind_output_handler(record_measurement)
        self.node.qmemory.subcomponents['qubit_detector_x'].ports['cout0'].bind_output_handler(record_measurement)

        # Await done signal from Alice
        yield self.await_port_input(self.node.ports[self.c_port])

        # All qubits sent, send bases back
        self.node.ports[self.c_port].tx_output(bases)

        # Await matched indices from Alice and process key
        yield self.await_port_input(self.node.ports[self.c_port])
        matched_indices = self.node.ports[self.c_port].rx_input().items
        final_key = []

        for i in matched_indices:
            if i < len(results):
                final_key.append(results[i])

        self.key = final_key
        global bob_keys
        bob_keys.append(final_key)
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
        secret_key = np.random.randint(2, size=self.key_size)
        bases = list(np.random.randint(2, size=self.key_size))

        # Transmit encoded qubits to Bob
        self.node.qmemory.subcomponents['qubit_source'].status = SourceStatus.INTERNAL
        for i, bit in enumerate(secret_key):
            # Await a qubit
            yield self.await_port_output(self.node.qmemory.subcomponents['qubit_source'].ports['qout0'])
            qubits = self.node.qmemory.subcomponents['qubit_source'].ports['qout0'].rx_output().items
            self.node.qmemory.put(qubits, positions=[0], replace=True)
            self.node.qmemory.execute_program(EncodeQubitProgram(bases[i], bit))
            yield self.await_program(self.node.qmemory)
            self.node.qmemory.pop(0)
            self.node.ports[self.q_port].tx_output(self.node.qmemory.ports['qout'].rx_output())
        self.node.qmemory.subcomponents['qubit_source'].status = SourceStatus.OFF

        # Signal end of transmission
        self.node.ports[self.c_port].tx_output('DONE')

        # Await response from Bob
        yield self.await_port_input(self.node.ports[self.c_port])
        bob_bases = self.node.ports[self.c_port].rx_input().items[0]
        matched_indices = []
        for i in range(self.key_size):
            if bob_bases[i] == bases[i]:
                matched_indices.append(i)

        self.node.ports[self.c_port].tx_output(matched_indices[:-1])
        final_key = []
        for i in matched_indices[:-1]:
            final_key.append(secret_key[i])
        self.key = final_key
        global alice_keys
        alice_keys.append(final_key)
        self.send_signal(signal_label=Signals.SUCCESS, result=final_key)


def run_experiment(fibre_length, dephase_rate, key_size, t_time=None, runs=100, q_source_probs=(1., 0.), loss=(0, 0)):
    if t_time is None:
        t_time = {'T1': 10001, 'T2': 10000}

    global bob_keys, alice_keys
    bob_keys = []
    alice_keys = []

    # ns.logger.setLevel(1)
    for _ in range(runs):
        ns.sim_reset()

        n = TwoPartyNetwork(fibre_length, dephase_rate, key_size, t_time, q_source_probs, loss).generate_noisy_network()
        node_a = n.get_node("alice")
        node_b = n.get_node("bob")
        p1 = KeySenderProtocol(node_a, key_size=key_size)
        p2 = KeyReceiverProtocol(node_b, key_size=key_size)

        p1.start()
        p2.start()

        ns.sim_run()

    def keys_match(key1, key2):
        if len(key1) != len(key2):
            return False

        for i in range(len(key1)):
            if key1[i] != key2[i]:
                return False
        return True

    _stats = {'MISMATCHED_KEYS': 0, 'MATCHED_KEYS': 0}
    for i, bob_key in enumerate(bob_keys):
        alice_key = alice_keys[i]
        if not keys_match(alice_key, bob_key):
            _stats['MISMATCHED_KEYS'] += 1
        else:
            _stats['MATCHED_KEYS'] += 1
    return _stats


if __name__ == '__main__':
    start = time.time()
    print(run_experiment(fibre_length=100,
                         dephase_rate=0,
                         key_size=200,
                         runs=10,
                         t_time={'T1': 11, 'T2': 10},
                         q_source_probs=[1., 0.],
                         loss=(0.001, 0.000)))
    print(f'Finished in {time.time() - start} seconds.')
