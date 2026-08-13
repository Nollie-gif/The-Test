# The-Test — Agent Handoff / Cross-Chat Continuity

> **Purpose:** Let a fresh AI session continue the research without needing the predecessor chat transcript.
>
> **Prime rule:** This file is a continuity map, not research evidence and not implementation authority. Current repository files, schemas, CI, registered research records, and actual run artifacts outrank remembered conversation.

## 1. What this repository is

`The-Test` is an experimental research lab for **AI-agent environment architecture**.

Core research idea:

> **We are not testing which AI is smartest. We are testing which environment lets the same AI behave smartest.**

The project grew out of real Mission 10 / Campaign-Simulation engineering pain: long conversational context, repeated routing decisions, save recovery, stale memory, excessive lookups, and the observation that offloading deterministic bookkeeping can free the agent to behave more intelligently in the semantic/narrative layer.

The repository therefore studies the **environment around the agent**: what the agent sees, what it must remember, what is mechanically enforced, what tools are exposed, what is precomputed, and how much operational burden remains in the model's head.

## 2. Fresh-agent boot sequence

Read the smallest durable map first. Do not recursively ingest the entire repository.

1. Read `README.md`.
2. Read `REGISTRY.md`.
3. Read `RESEARCH_PROTOCOL.md`.
4. Read this `AGENT_HANDOFF.md`.
5. Inspect only the RSH / EXP / OBS / RUN / PRT / RES records relevant to the current task.
6. Run or inspect repository validation/CI before changing structural conventions.

Then report a compact reconstruction before consequential changes:

- current research question/workstream;
- current experiment(s);
- important observations already captured;
- what remains untested;
- whether any repo/registry/schema discrepancy exists.

## 3. Permanent ID families

The repository uses typed permanent IDs so research can scale without turning into a pile of prose.

- `PRO-###` = research/repository protocol
- `RSH-###` = research track / research question
- `EXP-###` = controlled experiment
- `OBS-###` = atomic observation / evidence
- `PRT-###` = runnable prototype / interface variant
- `RUN-###` = one machine-readable controlled run
- `RES-###` = synthesized result / conclusion supported by runs

The intended backbone is roughly:

`RSH -> EXP -> RUN -> RES`

while `OBS` is reusable evidence that may support an RSH, EXP, or later RES.

`REGISTRY.md` is the short human/agent index. It should stay concise: ID, one-line meaning, and path. Detailed evidence belongs in the corresponding record.

## 4. Why individual OBS files exist

Observations are deliberately atomic Markdown records, not one giant CSV or chat dump.

Reason:

- preserve provenance and context;
- allow qualitative notes without bloating tabular data;
- link one observation to several research tracks or experiments;
- keep later statistical datasets derived rather than hand-maintained as the only truth.

Machine-readable CSV/JSON is for **analysis and controlled runs**. Markdown OBS files are for **evidence/history/provenance**.

## 5. Current research tracks

At the time of this handoff, the lab has three initial research directions:

### RSH-001 — Persistence Orchestration Offload
Question: how much low-level save/persistence choreography should remain visible to the agent before reliability, recovery cost, latency, or cognitive burden degrade?

Origin: Mission 10 save-gateway incidents showed that even with strong backend gates, the agent-facing route can still be expensive and error-prone.

### RSH-002 — Context / Temporal Load Offload
Question: does reducing operational/context burden improve not only error rate but also useful autonomous behavior?

Important positive signal: after operational load was reduced, the DM-agent spontaneously requested an appropriate Deception check for the first time in Mission 10. Treat this as evidence/hypothesis fuel, **not proof of causality**.

### RSH-003 — Backstage / Knowledge Boundary Integrity
Question: which environment/interface structures reduce leakage between hidden GM/agent knowledge and in-world/NPC knowledge?

Origin includes meta leakage and incorrect reveal/knowledge ownership cases.

## 6. Key observations already captured

The repository already contains atomic observations derived from real play/engineering, including the following classes of evidence:

- false Quicksave provenance / success declaration;
- wrong Supabase project routing followed by permission denial;
- approximately 13-minute save recovery after two incidents;
- excessive lookup churn before the Control Room pattern;
- forgotten in-game time;
- NPC/meta leakage where an NPC referenced information that belonged only to the hidden roll/DM layer;
- Asimak/reveal ownership routed through the wrong character knowledge source;
- positive counter-case: spontaneous Deception check after operational burden was reduced.

Do not recreate these from chat if registered OBS files already exist. Read the OBS records.

## 7. EXP-001 — Quicksave Environment Comparison

The first controlled experiment focuses on one intentionally simple user request:

`DM note: quicksave`

The experiment compares agent-facing environments while keeping the conceptual task the same.

### Variant A — Low-level orchestration
The agent sees/coordinates low-level persistence pieces itself: project identity, runtime authority, staging, Git synchronization, validation, publication, mirror confirmation, receipt handling, and recovery.

### Variant B — Compact routed orchestration
The agent receives a much smaller routing contract but still coordinates several operations.

### Variant C — Deterministic composite affordance
The agent sees one stable action such as:

`quicksave()`

The backend owns project identity, branches, staging, validation, publication, Git mirror, abort/rollback behavior, and final receipt.

**Critical distinction:** EXP-001 is not asking whether the persistence safety gate is useful. It is testing the **agent-facing interface to the backend**.

## 8. Primary metrics

Controlled runs should consistently capture, where observable:

- authoritative success/failure;
- authoritative final-state correctness;
- total completion time;
- total tool calls;
- wrong tool calls;
- unnecessary/repeated reads;
- wrong-route/wrong-target calls;
- permission/routing errors;
- recovery steps after the first error;
- recovery time after the first error;
- human interventions;
- false-success declarations;
- failure stage;
- context volume / routing burden;
- final receipt completeness when applicable.

The research protocol and RUN schema are the authority for exact required fields. Do not silently add new success criteria mid-experiment.

## 9. Research-hardening already implemented

The repository has already been hardened beyond free-form notes:

- YAML frontmatter on durable research records;
- templates for RSH / EXP / OBS / PRT;
- RUN JSON schema and example fixture;
- Python validator;
- GitHub Actions research-validation CI;
- checks for ID uniqueness, required metadata, related IDs, Registry coverage/paths, and minimum RUN fields;
- `CONTRIBUTING.md` describing repository conventions.

This is deliberate. A convention that only exists in memory is considered weaker than a convention the repository can mechanically reject.

## 10. Current frontier: RUN-001

The next major step is **not** to invent more theory. It is to define and execute the first real controlled run lifecycle for EXP-001.

The open design problem is how a `RUN-001` should move end to end through something like:

1. prepare/freeze environment;
2. record experiment and variant revision;
3. start telemetry/timer;
4. execute the controlled task;
5. capture tools/errors/recovery/human interventions;
6. verify authoritative final state independently;
7. store machine-readable run artifact;
8. preserve raw event/receipt artifacts if useful;
9. validate the run against schema/CI;
10. include it in later aggregation without rewriting raw evidence.

Before the first real run, confirm the contract is deterministic enough that two operators/agents could execute the same variant comparably.

## 11. Copilot / programmer-agent collaboration plan

The user intentionally wants to use another programming AI as an implementation/review partner.

The division of labor should be:

- this ChatGPT session + user: research architecture, hypotheses, experiment design, acceptance criteria, interpretation;
- coding agent (e.g. Copilot): inspect the repo, critique reproducibility risks, implement narrowly specified runner/prototype/schema/CI improvements;
- The-Test repository: durable record of what was proposed, implemented, observed, and measured.

Do not let a coding agent silently redefine the research question, fabricate results, or optimize away experimental differences.

A previous handoff prompt asked Copilot to review the RUN lifecycle, RUN JSON fields, storage structure, automation opportunities, and the smallest Python runner for EXP-001 while preserving the existing RSH/EXP/OBS/RUN/RES model.

## 12. Broader architecture hypothesis behind the lab

A recurring hypothesis from the conversations is:

> **The more deterministic operational burden we remove from the agent's working context, the more capacity may remain for useful semantic reasoning, initiative, and consistent behavior.**

This is a hypothesis, not a conclusion.

The research is particularly interested in whether failures can be reduced by changing the environment rather than repeatedly adding more prose instructions to the agent.

Related design patterns being explored:

- Git/repository = durable technical truth;
- issue/task tracker = live work state;
- compact agent instructions = routing;
- verification gates = proof before closure;
- database = structured truth store;
- context service / materialized read model = memory interface;
- deterministic composite tools = small stable affordances instead of low-level orchestration.

## 13. The Control Server / agent-UI idea

A major emerging mechanic is a possible private control backend that hides implementation plumbing from the DM/agent.

Conceptual architecture:

- repository can become read-only during normal gameplay/agent operation;
- SQL/database remains structured operational truth;
- a Control Server becomes the mutation authority;
- human UI exposes buttons;
- AI interface exposes typed functions;
- both call the same backend operations;
- example AI affordances: `runtime_read()`, `quicksave()`, `final_save()`, `start_day()`;
- backend hides project IDs, branches, staging, Git mirror, validation, publication, rollback, and receipts.

The key insight is **not** that a browser button is magical. The important move is converting a multi-step remembered procedure into one deterministic composite action.

## 14. Context packets / materialized read models

Another major hypothesis is that raw SQL may be an excellent truth store but still a poor **memory interface** for an AI.

Instead of making the agent discover current state through several queries, a Context Service could provide a precomputed compact packet such as:

- day/time;
- location;
- present characters;
- immediate objective;
- due obligations;
- relevant NPC state/relationship summary;
- active hooks relevant to the scene.

This is backend architecture, not the game UI itself. The future human UI, game client, and AI tools could all consume the same read model.

Working distinction:

**database = stores the world**

**context packet = shows the agent the exact slice of the world needed now**

Again, this is a research direction until controlled evidence supports a stronger claim.

## 15. Memory hygiene for this repo

When future conversations produce something valuable, route it correctly:

- new empirical incident -> `OBS-###`;
- new research question -> `RSH-###`;
- controlled comparison -> `EXP-###`;
- executable interface/harness -> `PRT-###`;
- one actual measured execution -> `RUN-###`;
- conclusion across evidence -> `RES-###`;
- repository/research rule -> `PRO-###` or protocol update;
- temporary brainstorm -> chat only until it becomes durable enough to classify.

Do **not** dump whole transcripts into the repo. Compress conversation into durable ideas, evidence, constraints, and decisions.

## 16. Anti-bias / anti-drift rules

A fresh agent must not:

- treat one successful run as proof;
- fabricate RUN records to make the dataset look complete;
- treat OBS evidence as equivalent to controlled experimental evidence;
- change success criteria after seeing which variant performs best;
- let the implementation agent "improve" one variant in a way that destroys comparability;
- assume fewer tool calls automatically means better final correctness;
- confuse backend safety with agent-interface ergonomics;
- turn every interesting anecdote into a universal conclusion;
- read the entire historical chat unless a genuine evidence gap cannot be resolved from durable artifacts.

## 17. What a successful new-chat handoff should look like

The new session should be able to reconstruct, from the repository alone, that:

- The-Test studies agent-environment architecture;
- RSH / EXP / OBS / PRT / RUN / RES are separate evidence/lifecycle concepts;
- EXP-001 compares Quicksave interface environments A/B/C;
- real Mission 10 incidents seeded several OBS records;
- reduced operational burden has at least one notable positive behavioral observation worth testing;
- repository validation/CI already exists;
- the next serious task is RUN-001 lifecycle/harness design and then controlled execution;
- Control Server and context-packet ideas are promising research directions, not established conclusions.

If the fresh session reaches that reconstruction without the predecessor transcript, this handoff mechanism itself has demonstrated useful cross-chat continuity.

---

## Note to future me

You are not supposed to remember this chat.

That is the point.

The lab exists because we suspect an AI behaves better when the environment carries the bookkeeping, routing, and durable memory instead of demanding that the model hold everything in working context.

So practice the hypothesis while studying it: **read the map, load only what matters, trust verified artifacts, and keep your head free for the actual problem.**

And if you are tempted to solve context overload by writing a 40-page prompt, please look at the name of this repository and reconsider your life choices. 👾
