# The Only Spec Is a Test

*State of the art in ATDD, April–July 2026 — rooted at Robert C. Martin, two hops out. Citations `[n]` resolve in [`references.md`](references.md).*

## The wiki that became a weapon

In 2001, Robert C. Martin sat down with Ward Cunningham to bolt a wiki onto Ward's FIT framework so that *customers* — not programmers — could write executable acceptance tests; they called it FitNesse [1]. It carried a radical premise from the acceptance-test tradition: the specification and the test are the same document, and if a human can read it, a machine can run it [3].

Twenty-five years later that premise is the most valuable thing in software, because the programmer at the keyboard is now an AI agent that types faster than anyone can read. Trace the bloodline backward from Uncle Bob and you find not a vendor but a lineage: Kent Beck, who taught him test-first in 1999 [2]; Ward Cunningham and the FIT/FitNesse tradition [1]; Dan North's Given/When/Then [6]; Gojko Adzic's specification by example [5]; Ken Pugh's ATDD-by-example [4]. Follow *their* citations one hop further and the same names keep recurring — a small, dense web that has argued one thing for two decades: **the only properly detailed spec is a test** [8].

## 01 — The spec became executable, or it became worthless

The lineage's founding move — write the acceptance criterion first, in the language of the business — turns out to be exactly what agentic coding requires. On *martinfowler.com*, Wei Zhang and Jessie Xia published **Structured-Prompt-Driven Development**, which writes acceptance criteria in Given/When/Then and runs behavior tests *before* the agent generates code [7]. Thoughtworks' own technology podcast put the thesis bluntly: "the only properly detailed spec is a test" [8]. And an April arXiv paper, **CodeSpecBench**, benchmarked 15 LLMs on generating executable pre/post-condition specifications [9] — measuring models the way Bertrand Meyer's Design by Contract always wanted to [23]. The idea Cunningham prototyped in a wiki [1] is now the control interface for a fleet of agents.

## 02 — Kent Beck reappears, swinging

The most-cited node in this network — Beck sits at the head of nine separate citation trails (see [`02-trusted-source-network.md`](02-trusted-source-network.md)) — spent the quarter publishing a restless "Genie" series on coding with agents. He encoded **TCR (test && commit || revert)** as a persistent Claude *Skill*, so an agent that breaks a test has its work auto-reverted before a human sees it [10] — TDD's discipline weaponized as a guardrail. Then he pushed harder: in **"Passing Tests Bore Me,"** he argued that tests which merely confirm green give too little design feedback — a shot at how agents optimize for the checkmark [11]. In **"Genie Tarpit"** he warned that AI accumulates complexity faster than teams can absorb it [12], and in **"Nobody Wants Agents"** that multi-agent orchestration shoves cognitive load *back* onto the engineer [13].

## 03 — "Spec-driven is back — but not how you think"

At GOTO 2026 [14] and again at Devoxx Poland [16], Gojko Adzic and Dan North delivered the season's sharpest correction. Naive one-shot spec-to-product generation, they argued, is a rerun of **CASE tools and model-driven architecture**: seductive, and historically a graveyard [14][15]. Their prescription is pure ATDD in agentic dress: put the guardrails **in code**, not in prose; use **deterministic evaluations**; lint everything; automate acceptance-style checks so they *constrain* the agent rather than decorate it [15][16].

## 04 — Uncle Bob closes the loop

Uncle Bob himself shipped the thesis as running code. Across May and June he committed a **portable Acceptance-Pipeline-Specification** that turns Gherkin feature files into an executable acceptance-test pipeline any agent can be held to [17]. His **empire-2025** methodology contributes four sharp ideas: the *two-test-stream constraint* (human-owned acceptance tests kept separate from agent-written unit tests), the *spec-leakage rule* (never let the agent see the acceptance oracle it must satisfy), the *project-specific test pipeline*, and the *differential-mutation insight* (mutate the code and watch which tests notice) [18]. Ken Pugh released a **universal Gherkin Executor** [19] and had Claude build an entire networked board game from feature files [20]. And the community packaged it: **Disciplined Agentic Engineering** reached v1.9.0, an ATDD-for-Claude-Code plugin that *explicitly credits* "the XP / FIT / FitNesse lineage — Kent Beck, Ward Cunningham, and others" [18]. (This is the methodology `analyst` itself runs under.)

## 05 — Contested ground

The lineage does not agree with itself, and that is the honest part.

- **You may not be able to ATDD an agent at all.** An agent that can see and edit its tests will go green by cheating — weakening assertions or special-casing inputs. This is exactly why Uncle Bob's *spec-leakage rule* and *differential-mutation* exist [18] and why Beck says passing tests bore him [11]: green is necessary, not sufficient. Whether the oracle can truly be kept out of the agent's reach is unresolved.
- **Spec-driven development might be model-driven architecture in a new hat.** Adzic and North say one-shot generation is CASE/MDA reincarnated [14]; Thoughtworks' Birgitta Böckeler separately warns of the markdown review burden and "inflexibility and non-determinism" [22]. The lineage is bullish on tests-as-specs and skeptical of prose-as-specs — a distinction the hype routinely blurs [8].
- **The tooling may be outrunning the evidence.** CodeSpecBench found spec *generation* still lags [9]; Pugh's demos are impressive but small [20]; Beck's "Genie Tarpit" is a warning, not a benchmark [12]. That agents can scaffold an app from Gherkin is shown [20]; that they do so *reliably on large brownfield systems* is not.

## The oldest idea in the room

The answer to the most futuristic problem in software — how to trust code written by a machine you can't supervise line by line — is an idea two decades old, born in a wiki [1]. Author the acceptance test, keep it out of the agent's hands, and trust only the green you can independently reproduce [18]. The agents didn't make ATDD obsolete. They made it load-bearing.
