# TRB-001 — Responses transport interruption

**Record type:** Troubleshooting / operational learning record  
**Date:** 2026-08-16  
**Related work:** PILOT-001, PILOT-002, PILOT-003, PILOT-003B  
**Status:** OFFLINE DIAGNOSIS COMPLETE — ROOT CAUSE UNKNOWN  
**Evidence class:** Redacted non-billable diagnostic evidence; not a canonical RUN

## Purpose

Preserve what was learned from the first live-pilot troubleshooting sequence without rewriting uncertainty into certainty. This record exists so a future operator can continue from durable evidence rather than reconstructing the incident from chat history.

The project treats failed and interrupted work as useful evidence when its limits are recorded honestly.

## Incident boundary

PILOT-001, PILOT-002, and PILOT-003 each reached a durable `request_started` / `api_request_started` boundary, but no model response was confirmed. They remain terminal `INCOMPLETE/UNKNOWN` and must not be retried, resumed, replayed, promoted, or reinterpreted as successful evidence.

Temporary API credentials used during the pilot sequence were revoked/deleted. No credential is preserved here.

## Known prior finding

A locally unusable `SSLKEYLOGFILE` configuration was discovered during troubleshooting. Windows Python 3.14 honored that setting while constructing its TLS context. PR #15 added an offline fail-closed TLS preflight so this condition is detected before a live trial opens.

That finding establishes a real failure mode, but it does **not** prove that it explains every interrupted pilot. A later live attempt still ended `UNKNOWN/INCOMPLETE` after `request_started`. Therefore the overall historical root cause remains unknown.

An active VPN was also observed during part of historical troubleshooting and was later disconnected. This is a clue only, not causal proof.

## PILOT-003B offline diagnostic snapshot

On 2026-08-16 the operator performed a bounded, non-billable diagnostic sequence. No API key was created or used, no model response was requested, and no raw logs or personal paths are preserved in this record.

Observed current state:

1. Active network adapters showed the physical Ethernet interface plus normal Hyper-V/WSL virtual adapters. No obvious active VPN adapter was present.
2. WinHTTP reported direct access with no proxy server.
3. No environment variables matching `PROXY`, `SSL`, `CERT`, or `VPN` were present. In particular, the previously problematic `SSLKEYLOGFILE` was not currently set.
4. Ordinary Python HTTPS to a neutral public endpoint completed with HTTP 200.
5. Unauthenticated reachability to the OpenAI API completed with the expected HTTP 401.
6. Python `urllib`, the same standard-library HTTP family used by the project driver, also reached the OpenAI API and received HTTP 401.
7. An unauthenticated Python `urllib` POST to `/v1/responses` reached the endpoint and received HTTP 401. This exercised the relevant endpoint and transport family without authorizing model execution.
8. Runtime reported Python 3.14.7 with OpenSSL 3.5.7.
9. Windows firewall profiles were enabled; no explicit outbound-block policy was identified by the bounded profile check.
10. `urllib.request.getproxies()` returned an empty mapping.
11. Windows security registration showed Windows Defender and Bitdefender Antivirus. Bitdefender services, including its VPN service, were running, but a running service is not evidence of an active VPN tunnel.
12. Enabled bindings on the physical Ethernet adapter showed standard Microsoft networking components; no obvious Bitdefender-specific adapter binding appeared in the bounded check.
13. Windows `Get-VpnConnection` returned no configured connection in the checked context.
14. TCP connectivity to `api.openai.com:443` succeeded.

## Interpretation

The historical failure is **not reproducible as a persistent basic transport failure under the current environment**.

At the time of this snapshot, the machine could resolve/connect over TCP 443, establish TLS, use Python HTTPS, use Python `urllib`, reach OpenAI, and reach the Responses endpoint sufficiently to receive the expected unauthenticated rejection.

This narrows the investigation but does not identify a historical root cause. Remaining explanations may include intermittent or state-dependent VPN behavior, endpoint-security inspection, firewall/network state, transient transport interruption, or another condition not observable in the bounded snapshot.

No listed hypothesis should be promoted to root cause without new evidence.

## Safety and evidence rules established

- Do not create a new API key merely to diagnose this incident.
- Do not make another paid/model request under PILOT-003B.
- Do not preserve secrets, API response bodies, raw exception text, personal paths, hostnames, IP addresses, or raw logs in troubleshooting evidence.
- Prefer allowlisted categories and boolean/status observations over raw diagnostic dumps.
- A successful current connectivity check does not retroactively convert an `UNKNOWN` historical request into success or failure.
- Terminal pilot artifacts remain immutable.
- `RUN-001` remains locked.
- Any future live pilot requires explicit human review and separate authorization after diagnosis and safeguards are reviewed.

## Engineering consequence

PR #15 already hardened the known `SSLKEYLOGFILE` failure mode with a preflight safeguard. PILOT-003B did not establish another sufficiently specific code defect to justify speculative code changes.

If future work requires better discrimination after `request_started`, design the smallest privacy-preserving diagnostic instrumentation first. It should record only pre-approved transport categories and lifecycle boundaries, never secrets or arbitrary exception/log content.

## Research lesson

This incident is useful precisely because it did not produce a clean answer. The first live-pilot sequence exposed a distinction the research system must preserve:

> **Observed failure mode is not the same thing as proven root cause. Current health is not proof of historical health. Unknown is a valid terminal result.**

The operational workflow therefore becomes part of the research method: preserve terminal uncertainty, diagnose offline first, harden only demonstrated failure modes, and require a human gate before spending money or generating new evidence.

## Continuation point

PILOT-003B basic offline transport diagnosis is complete. Before any future pilot, human review should decide whether the current evidence is sufficient to close the troubleshooting task or whether a separate, narrowly scoped privacy-preserving instrumentation task is warranted.

After the transport issue is formally dispositioned, research-design work resumes with the already-established priorities: define coding rules for every EXP-001 metric; freeze model, prompt, task, and analysis procedure; require at least 10 runs per variant; add at least one clearly non-game task for external validity; and publish EXP-001 even if the result is null or unexciting.
