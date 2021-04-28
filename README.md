# QKD Simulations with Noise Models and Error Reconcillation  

In this library, we aim to implement the full stack of quantum key distribution (QKD). QKD involves the following steps:

1. Raw key distribution: Distributing quantum states over a quantum channel with a certain protocol such an eavesdropper can be detected if there is one.
2. Quantum bit error rate (QBER) estimation: Estimating the quality of the quantum channel. This can be done with less frequency but depending on the medium should be performed regularly for any changes to the channel. For example over the air transmissions can change based on the weather and can influence the QBER. 
3. Information reconciliation: During transmission, quantum bits are influenced by the error in the channel. One can run protocols to correct for bits that are flipped due to noise. This stage leaks information to any eavedroppers which motivates the next stage.
4. Privacy amplification: To recover secrecy lost due to information reconciliation, privacy amplification can be performed.

We implement these stages in simulation using various modern methods. We use the quantum simulator NetSquid [1] as the engine to our simulations.

[1] Coopmans, Tim, et al. "NetSquid, a discrete-event simulation platform for quantum networks." arXiv preprint arXiv:2010.12535 (2020).
