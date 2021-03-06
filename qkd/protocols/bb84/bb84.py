import netsquid as ns
import netsquid.components.instructions as instr
import numpy as np
from netsquid.components import QuantumProgram
from netsquid.protocols import NodeProtocol, Signals

from qkd.networks import TwoPartyNetwork


class EncodeQubitProgram(QuantumProgram):
    """
    Program to encode a bit according to a secret key and a basis.
    """

    default_num_qubits = 1

    def __init__(self, base, bit):
        super().__init__()
        self.base = base
        self.bit = bit

    def program(self):
        q1, = self.get_qubit_indices(1)
        self.apply(instr.INSTR_INIT, q1)
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
        for i in range(self.key_size):
            # Await a qubit from Alice
            yield self.await_port_input(self.node.ports[self.q_port])

            # Measure in random basis
            if bases[i] == 0:
                res = self.node.qmemory.execute_instruction(instr.INSTR_MEASURE, output_key="M")
            else:
                res = self.node.qmemory.execute_instruction(instr.INSTR_MEASURE_X, output_key="M")
            yield self.await_program(self.node.qmemory)
            results.append(res[0]['M'][0])
            self.node.qmemory.reset()

            # Send ACK to Alice to trigger next qubit send (except in last transmit)
            if i < self.key_size - 1:
                self.node.ports[self.c_port].tx_output('ACK')

        # All qubits arrived, send bases
        self.node.ports[self.c_port].tx_output(bases)

        # Await matched indices from Alice and process key
        yield self.await_port_input(self.node.ports[self.c_port])
        matched_indices = self.node.ports[self.c_port].rx_input().items
        final_key = []
        for i in matched_indices:
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
        secret_key = np.random.randint(2, size=self.key_size)
        bases = list(np.random.randint(2, size=self.key_size))

        # Transmit encoded qubits to Bob
        for i, bit in enumerate(secret_key):
            self.node.qmemory.execute_program(EncodeQubitProgram(bases[i], bit))
            yield self.await_program(self.node.qmemory)

            q = self.node.qmemory.pop(0)
            self.node.ports[self.q_port].tx_output(q)
            if i < self.key_size - 1:
                yield self.await_port_input(self.node.ports[self.c_port])

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
            final_key.append(secret_key[i])
        self.key = final_key
        self.send_signal(signal_label=Signals.SUCCESS, result=final_key)


if __name__ == '__main__':
    n = TwoPartyNetwork().generate_noiseless_network()
    node_a = n.get_node("alice")
    node_b = n.get_node("bob")

    p1 = KeySenderProtocol(node_a, key_size=100)
    p2 = KeyReceiverProtocol(node_b, key_size=100)

    p1.start()
    p2.start()

    stats = ns.sim_run()

    print(len(p1.key))
    print(p1.key)
    print(p2.key)
