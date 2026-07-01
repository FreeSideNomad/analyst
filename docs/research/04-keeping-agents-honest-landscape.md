# Keeping Agents Honest — The Landscape

ATDD/DAE is one school of thought. "Keeping agents honest" is not one problem: different schools attack different failure modes — *wrong* code, *reward-hacked* objectives, *deceptive* reasoning, *prompt-injected* behavior, or a deliberately *scheming* model. This maps the legitimate frontiers.

*Synthesis from knowledge through early 2026; named works are cited where confidently known. Not the product of the verified research run above — treat as an orientation map.*

## 1. Execution-grounded verification (DAE's own family)
Ground truth the agent can't argue with.
- **ATDD / acceptance oracles** — the DAE approach.
- **Property-based & metamorphic testing** (QuickCheck/Hypothesis) — assert *properties* over generated adversarial inputs, so example tests can't be special-cased.
- **Formal methods + LLMs** — Dafny, Lean, TLA+, Design by Contract. Proof instead of tests; "verified code generation" is the strongest form.
- **Mutation testing** — "testing the tests."

## 2. Independent checking & the generator–verifier gap
Verification is easier than generation, so use a separate adversarial checker.
- **LLM-as-judge / verifier models**, self-consistency.
- **AI Safety via Debate** (Irving et al. 2018; revived empirically by Khan et al. 2024, "Debating with more persuasive LLMs").
- **Adversarial multi-vote verification** — N independent skeptics prompted to *refute* (the method used in this research). The sophistication is ensuring verifier independence.

## 3. Process supervision over outcome supervision
Reward the *reasoning*, not just the answer.
- **OpenAI, "Let's Verify Step by Step"** (Lightman et al. 2023) — process reward models beat outcome reward models and reduce spec-gaming.

## 4. Scalable oversight (train it honest)
Bootstrap oversight of work humans can't check directly.
- **Constitutional AI / RLAIF** (Anthropic 2022), **weak-to-strong generalization** (OpenAI / Burns et al. 2023), recursive reward modeling.

## 5. Chain-of-thought monitoring & interpretability
Watch the reasoning, not just the output.
- **"Chain of Thought Monitorability"** (Korbak et al. 2025) — a cross-lab position paper: CoT legibility is a fragile but real safety asset; don't optimize it away.
- Anthropic's own finding that **CoT is often unfaithful** ("models don't always say what they think") — monitoring is necessary but not sufficient.
- Interpretability: deception/lie probes, activation steering, sparse-autoencoder features. Frontier, not yet dependable.

## 6. AI Control (assume it's adversarial)
The most advanced *systems* thinking about untrusted agents.
- **Redwood Research's "AI Control"** (Greenblatt, Shlegeris et al., 2023–25): even if the model is scheming, design protocols — **trusted monitoring, untrusted monitoring, resampling, defer-to-trusted** — that bound risk, measured by **control evaluations** (a red team plays the scheming model). Reframes "honest" as "safe even if dishonest."
- Related: **Anthropic sabotage evaluations** (2024).

## 7. Capability control / least privilege (security camp)
An agent that *can't* do harm needn't be trusted not to.
- **Simon Willison's "lethal trifecta"** (2025) — danger = private data + untrusted content + exfiltration; remove one leg.
- **CaMeL** (Debenedetti et al., DeepMind 2025, "Defeating Prompt Injections by Design") — capability-based isolation.
- Sandboxing, deterministic gates, human approval on side effects, secret-blocking.

## 8. Evals & auditing
You can't manage what you don't measure.
- **METR** autonomy / dangerous-capability evals, model-written evals, alignment audits, red-teaming.

## Failure-mode map

| Failure mode | Best-in-class school |
|---|---|
| Code is *wrong* | Execution-grounded verification (§1), independent checking (§2) |
| Model *reward-hacks* | Process supervision (§3), scalable oversight (§4) |
| Reasoning is *deceptive* | CoT monitoring + interpretability (§5) |
| Model is *scheming* | AI Control protocols (§6) |
| *Prompt injection* / exfiltration | Capability control & least privilege (§7) |

## Takeaway for `analyst`

DAE is a strong answer to row 1 (and, via the human-owned oracle, part of row 2). It says almost nothing about rows 3–5. The genuinely advanced posture is a **stack**: execution-grounded oracle + independent adversarial verifier + least-privilege sandbox + monitoring, evaluated under a control-style "assume it's lying" threat model. For this repo, the highest-value gap that DAE/CI/review does **not** already cover is the CHARTER **governance boundary** (§7 territory) — see [`05-controls-decision.md`](05-controls-decision.md).
