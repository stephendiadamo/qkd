import netsquid as ns
import numpy as np
import matplotlib.pyplot as plt

from qkd.networks import TwoPartyNetwork
from qkd.protocols.bb84 import KeySenderProtocol as BB84Sender, KeyReceiverProtocol as BB84Receiver
from qkd.protocols.e91 import KeySenderProtocol as E91Sender, KeyReceiverProtocol as E91Receiver
from qkd.reconciliation import cascade

bob_keys = []
alice_keys = []
bob_corrected_keys = []


def run_e91_experiment(correction=True):
    protocols = [E91Sender, E91Receiver]
    return run_experiment(protocols,
                          fibre_length=25000,
                          dephase_rate=0.5,
                          t_time={'T1': 11, 'T2': 10},
                          key_size=300,
                          q_source_probs=[1., 0.],
                          # loss=(0.001, 0.0001),
                          correction=correction,
                          runs=10)


def run_bb84_experiment(correction=True):
    protocols = [BB84Sender, BB84Receiver]

    return run_experiment(protocols,
                          fibre_length=25000,
                          dephase_rate=0.5,
                          t_time={'T1': 11, 'T2': 10},
                          key_size=300,
                          q_source_probs=[1., 0.],
                          # loss=(0.001, 0.0001),
                          correction=correction,
                          runs=10)


def run_b92_experiment():
    raise Exception('Noisy version of B92 not yet implemented')
    # protocols = [B92Sender, B92Receiver]
    # return run_experiment(protocols,
    #                       fibre_length=10,
    #                       dephase_rate=0,
    #                       key_size=100,
    #                       runs=10)


def plot_loss_experiment(protocols, runs=100):
    lengths = np.linspace(0, 10, 6)
    losses = np.linspace(0, 0.01, 5)
    for loss in losses:
        data = []
        for length in lengths:
            print(f'Running l={length}, p_loss={loss}')
            ns.sim_reset()
            data.append(run_experiment(
                protocols=protocols,
                fibre_length=length,
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


def plot_key_length_vs_length(protocols, runs=100):
    lengths = np.linspace(0, 10, 5)
    sizes = np.linspace(15, 100, 4, dtype=int)
    for size in sizes:
        data = []
        for length in lengths:
            print(f'Running l={length}, size={size}')
            ns.sim_reset()
            data.append(run_experiment(
                protocols=protocols,
                fibre_length=length,
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


def plot_fibre_length_experiment(protocols, runs=5):
    lengths = np.linspace(100, 20000, 5)
    phases = np.linspace(0, 0.5, 4)
    key_size = 200
    for phase in phases:
        data = []
        for length in lengths:
            print(f'Running l={length}, p={phase}')
            ns.sim_reset()
            data.append(run_experiment(
                protocols=protocols,
                fibre_length=length,
                dephase_rate=phase,
                key_size=key_size,
                runs=runs,
                t_time={'T1': 11, 'T2': 10},
                q_source_probs=[1., 0.]))
        correct_keys = [d['MATCHED_KEYS'] / runs for d in data]
        plt.plot([l / 1000 for l in lengths], correct_keys,
                 marker='.',
                 linestyle='solid',
                 label=f'Dephase Rate={"%.2f" % phase}')
        ax = plt.gca()
        line = ax.lines[-1]
        print(line.get_xydata())

    plt.title(f'Key Distribution Efficiency Over Fibre: Key size {key_size}')
    plt.ylim(0, 1.1)
    plt.xlabel('Length (km)')
    plt.ylabel('Percentage of correctly transmitted keys')
    plt.legend()
    plt.show()


def run_experiment(protocols, fibre_length, dephase_rate, key_size, t_time=None, runs=100, q_source_probs=(1., 0.),
                   loss=(0, 0), correction=False):
    if t_time is None:
        t_time = {'T1': 11, 'T2': 10}

    global bob_keys, alice_keys, bob_corrected_keys
    bob_keys = []
    alice_keys = []
    bob_corrected_keys = []

    for _ in range(runs):
        ns.sim_reset()
        # ns.logger.setLevel(1)
        n = TwoPartyNetwork('network',
                            fibre_length,
                            dephase_rate,
                            key_size,
                            t_time,
                            q_source_probs,
                            loss).generate_noisy_network()

        node_a = n.get_node("alice")
        node_b = n.get_node("bob")

        p1 = protocols[0](node_a, key_size=key_size)
        p2 = protocols[1](node_b, key_size=key_size)
        p1.start()
        p2.start()

        ns.sim_run()

        alice_keys.append(p1.key)
        bob_keys.append(p2.key)

        if correction:
            c1 = cascade.SenderProtocol(node_a, key=alice_keys[-1])
            c2 = cascade.ReceiverProtocol(node_b, key=bob_keys[-1])

            c1.start()
            c2.start()

            ns.sim_run()
            bob_corrected_keys.append(c2.cor_key)

    def keys_match(key1, key2):
        if len(key1) != len(key2):
            return False
        for j in range(len(key1)):
            if key1[j] != key2[j]:
                return False
        return True

    def qber(key1, key2):
        matched = 0
        for j in range(len(key1)):
            if key1[j] == key2[j]:
                matched += 1
        return 1 - matched / len(key1)

    _stats = {'MISMATCHED_KEYS': 0, 'MATCHED_KEYS': 0, 'CORRECTED_MATCHED': 0, 'AVG_QBER': 0}
    for i, bob_key in enumerate(bob_keys):
        alice_key = alice_keys[i]
        if not keys_match(alice_key, bob_key):
            _stats['MISMATCHED_KEYS'] += 1
        else:
            _stats['MATCHED_KEYS'] += 1
        _stats['AVG_QBER'] += qber(bob_key, alice_key) / len(bob_keys)

    for i, bob_key in enumerate(bob_corrected_keys):
        alice_key = alice_keys[i]
        if keys_match(alice_key, bob_key):
            _stats['CORRECTED_MATCHED'] += 1

    _stats['AVG_QBER'] = int(1e5 * _stats['AVG_QBER']) / 1e5
    return _stats


if __name__ == "__main__":
    print(run_e91_experiment())
    print(run_bb84_experiment())
    # plot_fibre_length_experiment([E91Sender, E91Receiver])
