---
id: OBS-003
title: Control Room Reduced Lookup Pressure
status: HISTORICAL
related_ids: [RSH-002, OBS-004, OBS-008]
date: 2026-08-13
author: Nollie + ChatGPT
---
# OBS-003 — Control Room Reduced Lookup Pressure

## Evidence class

Real-play observation.

## Source system

Mission 10 DM Control Room playtest.

## Observation

The DM Control Room introduced a compact routing rule: classify the request, read the smallest authoritative source, then use only that path.

During play, this reduced repeated broad repository lookups and encouraged the agent to keep scene essentials in local context until a genuine boundary or uncertainty appeared.

The key behavioral instruction was effectively:

- load authoritative scene/runtime state once;
- use targeted reads only when exact canon/mechanics matter;
- do not reopen tools for every micro-beat.

## Why this matters to The-Test

This is an early example of an **agent interface changing behavior without changing the underlying source of truth**.

The repository and database remained authoritative. What changed was the routing surface presented to the agent.

## Candidate interface lesson

A compact entry map can reduce cognitive/tool churn, but it still depends on the agent following instructions. The-Test should compare this instruction-based approach against deterministic context services and typed tools.

## Related records

- RSH-002
- PRO-001
- OBS-004
- OBS-008

## Research status

Historical source observation; candidate baseline for future retrieval experiments.
