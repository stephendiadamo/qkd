import time

import netsquid as ns
import numpy as np
import matplotlib.pyplot as plt
import reconciliation
from qkd.networks import TwoPartyNetwork
from qkd.bb84 import KeySenderProtocol as BB84Sender, KeyReceiverProtocol as BB84Receiver
from qkd.b92 import KeySenderProtocol as B92Sender, KeyReceiverProtocol as B92Receiver

bob_keys = []
alice_keys = []
bob_corrected_keys = []


def run_bb84_experiment():
    protocols = [BB84Sender, BB84Receiver]
    return run_experiment(protocols,
                          fibre_length=10,
                          dephase_rate=0,
                          key_size=100,
                          runs=10)


def run_b92_experiment():
    protocols = [B92Sender, B92Receiver]
    raise Exception('Noisy version of B92 not yet implemented')
    # return run_experiment(protocols,
    #                       fibre_length=10,
    #                       dephase_rate=0,
    #                       key_size=100,
    #                       runs=10)


def plot_loss_experiment(runs=100):
    lengths = np.linspace(0, 10, 6)
    losses = np.linspace(0, 0.01, 5)
    for loss in losses:
        data = []
        for length in lengths:
            print(f'Running l={length}, p_loss={loss}')
            ns.sim_reset()
            data.append(run_experiment(fibre_length=length,
                                       dephase_rate=0,
                                       key_size=25,
                                       runs=runs,
                                       t_time={'T1': 11, 'T2': 10},
                                       q_source_probs=[1., 0.],
                                       loss=(0, loss)),
                        )
        correct_keys = [d['MATCHED_KEYS'] / runs for d in data]
        plt.plot([l / 1000 for l in lengths], correct_keys,
                 marker='.',
                 linestyle='solid',
                 label=f'Loss Rate={loss}')
        plt.legend()
        plt.title('Key Distribution Efficiency Over Fibre')
        plt.ylim(0, 1.1)
        plt.xlabel('Length (km)')
        plt.ylabel('Percentage of correctly transmitted keys')
    plt.show()


def plot_key_length_vs_length(runs=100):
    lengths = np.linspace(0, 10, 5)
    sizes = np.linspace(15, 100, 4, dtype=int)
    for size in sizes:
        data = []
        for length in lengths:
            print(f'Running l={length}, size={size}')
            ns.sim_reset()
            data.append(run_experiment(fibre_length=length,
                                       dephase_rate=0,
                                       key_size=size,
                                       runs=runs,
                                       t_time={'T1': 11, 'T2': 10},
                                       q_source_probs=[1., 0.],
                                       loss=(0, 0.01)),
                        )
        correct_keys = [d['MATCHED_KEYS'] / runs for d in data]
        plt.plot([l / 1000 for l in lengths], correct_keys,
                 marker='.',
                 linestyle='solid',
                 label=f'Key Size={size}')
        plt.legend()
        plt.title('Key Distribution Efficiency Over Fibre')
        plt.ylim(0, 1.1)
        plt.xlabel('Length (km)')
        plt.ylabel('Percentage of correctly transmitted keys')
    plt.show()


def plot_fibre_length_experiment(runs=100):
    lengths = np.linspace(100, 1000, 4)
    phases = np.linspace(0, 0.5, 4)
    for phase in phases:
        data = []
        for length in lengths:
            print(f'Running l={length}, p={phase}')
            ns.sim_reset()
            data.append(run_experiment(fibre_length=length,
                                       dephase_rate=phase,
                                       key_size=50,
                                       runs=runs,
                                       t_time={'T1': 11, 'T2': 10},
                                       q_source_probs=[1., 0.]))
        correct_keys = [d['MATCHED_KEYS'] / runs for d in data]
        plt.plot([l / 1000 for l in lengths], correct_keys,
                 marker='.',
                 linestyle='solid',
                 label=f'Dephase Rate={phase}')
        plt.legend()
        plt.title('Key Distribution Efficiency Over Fibre')
        plt.ylim(0, 1.1)
        plt.xlabel('Length (km)')
        plt.ylabel('Percentage of correctly transmitted keys')
    plt.show()


def run_experiment(protocols, fibre_length, dephase_rate, key_size, t_time=None, runs=100, q_source_probs=(1., 0.),
                   loss=(0, 0)):
    if t_time is None:
        t_time = {'T1': 10001, 'T2': 10000}

    global bob_keys, alice_keys, bob_corrected_keys
    bob_keys = []
    alice_keys = []
    bob_corrected_keys = []

    for _ in range(runs):
        ns.sim_reset()

        n = TwoPartyNetwork(fibre_length, dephase_rate, key_size, t_time, q_source_probs, loss).generate_network()

        node_a = n.get_node("alice")
        node_b = n.get_node("bob")
        p1 = protocols[0](node_a, key_size=key_size)
        p2 = protocols[1](node_b, key_size=key_size)

        p1.start()
        p2.start()

        ns.sim_run()

        alice_keys.append(p1.key)
        bob_keys.append(p2.key)

        c1 = reconciliation.cascade.SenderProtocol(node_a, key=alice_keys[-1])
        c2 = reconciliation.cascade.ReceiverProtocol(node_b, key=bob_keys[-1])

        c1.start()
        c2.start()

        ns.sim_run()
        bob_corrected_keys.append(c2.corrected_key)

    def keys_match(key1, key2):
        if len(key1) != len(key2):
            return False
        for j in range(len(key1)):
            if key1[j] != key2[j]:
                return False
        return True

    _stats = {'MISMATCHED_KEYS': 0, 'MATCHED_KEYS': 0, 'CORRECTED_MATCHED': 0}
    for i, bob_key in enumerate(bob_keys):
        alice_key = alice_keys[i]
        if not keys_match(alice_key, bob_key):
            _stats['MISMATCHED_KEYS'] += 1
        else:
            _stats['MATCHED_KEYS'] += 1

    for i, bob_key in enumerate(bob_corrected_keys):
        alice_key = alice_keys[i]
        if keys_match(alice_key, bob_key):
            _stats['CORRECTED_MATCHED'] += 1
    return _stats


if __name__ == "__main__":
    print(run_b92_experiment())
