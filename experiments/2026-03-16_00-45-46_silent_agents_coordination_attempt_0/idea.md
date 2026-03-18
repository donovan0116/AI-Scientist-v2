## Name

silent_agents_coordination

## Title

The Power of Silence: Can Observational-Only Agents Enhance Multi-Agent Coordination?

## Short Hypothesis

In cooperative multi-agent reinforcement learning, introducing 'silent agents'—agents that can observe but not act—during centralized training can improve the coordination and performance of the acting agents by providing richer global perspectives, without increasing the complexity of decentralized execution. This is the best setting to investigate because it isolates the value of pure observational information in a CTDE paradigm, distinct from communication or action-based roles; simpler alternatives like adding more active agents would increase action space complexity, while our approach tests if 'free' observation alone is beneficial.

## Related Work

Related work includes: (1) Centralized Training with Decentralized Execution (CTDE) methods like MADDPG, QMIX, which use centralized critics but assume all agents act. (2) Communication in MARL, where agents learn to send messages to aid coordination. Our proposal differs by introducing agents with no action capacity, thus no communication or action learning—they are passive observers only during training. (3) Multi-agent systems with heterogeneous agents, but typically all have some action role. Our work is not a trivial extension because it questions the necessity of action for contribution in MARL, and systematically studies the impact of 'observation-only' entities.

## Abstract

Multi-agent reinforcement learning (MARL) often assumes all agents are capable of both observation and action. However, in many real-world systems, some entities may serve as passive sensors or observers without direct actuation capability. This paper investigates the role of 'silent agents'—agents that observe but cannot act—in cooperative MARL. We hypothesize that incorporating silent agents during centralized training can enhance the coordination of acting agents by providing additional observational perspectives, without complicating decentralized execution. We test this in standard cooperative MARL benchmarks (e.g., Multi-Agent Particle World) using CTDE algorithms like MADDPG. We vary the proportion of silent agents and measure coordination metrics (e.g., collective reward, social welfare) and sample efficiency. Our results show that silent agents can significantly improve performance, especially in partially observable environments, offering a novel approach to scalable MARL where observational resources are cheap but actions are costly.

## Experiments

1. **Environment**: Cooperative navigation task in Multi-Agent Particle World (MPE). N agents must cover N landmarks. We define a total agent pool (e.g., 6 agents), with a subset as 'acting agents' (e.g., 3) and the rest as 'silent agents' (e.g., 3). Silent agents have full observation but no action space; they are ignored during execution.
2. **Baseline**: All agents are acting (no silent agents). Use MADDPG (CTDE) as base algorithm.
3. **Intervention**: Train with silent agents included in the centralized critic. The critic receives observations from all agents (acting + silent). The actors only for acting agents.
4. **Variations**: (a) Vary the ratio of silent to acting agents (0%, 25%, 50%, 75%). (b) Test in fully vs. partially observable settings.
5. **Evaluation Metrics**: (a) Average episode return (collective reward). (b) Sample efficiency (learning curves). (c) Coordination metrics (e.g., distance to landmarks, collisions). (d) Ablation: compare to baseline with same number of acting agents but no silent agents (i.e., just fewer agents).
6. **Algorithmic Details**: Modify MADDPG: the centralized Q-function takes concatenated observations from all agents. Only acting agents have policy networks and contribute actions. Silent agents' observations are included but their actions are set to zero or omitted.

## Risk Factors And Limitations

1. **Risk**: Silent agents may provide redundant information, offering no benefit or even adding noise. Mitigation: Test in partially observable environments where extra perspectives are valuable.
2. **Risk**: The training complexity increases with more agents (more observations), potentially slowing learning. Mitigation: Use small numbers of silent agents.
3. **Limitation**: The study is limited to cooperative tasks; competitive or mixed settings may differ.
4. **Limitation**: We assume silent agents are 'free'—in reality, they may have cost (e.g., deployment, energy).
5. **Limitation**: The approach may not scale to very large numbers of silent agents due to input dimensionality to the critic.

