"""Step handlers for feature 013 — data normalization detection.

Detection/apply/revoke scenarios bind over the in-process seam (a real
StoreRepository + DatasetStore in the scenario tmp_path; "the app restarts"
rebuilds the repository over the same data dir, exactly as production boot
does). The workbench flow binds to Playwright against the fixtures app (a
seeded proposal on the sample sales table). Deterministic — detection is
local, no model calls.
"""

from __future__ import annotations

import os
import re
from typing import Any

from acceptance.e2e_base import (
    _STACK,
    ScenarioContext,
    _e2e_fresh,
    _e2e_stack,
    expect_,
    make_registry,
)
from analyst.api.repository import StoreRepository
from analyst.domain.normalization import UnknownNormalizationError

step, run_step = make_registry()
_expect = expect_

__all__ = ["ScenarioContext", "run_step", "_e2e_stack", "_e2e_fresh"]


# --------------------------------------------------------------------------- #
# State + seam
# --------------------------------------------------------------------------- #
def _state(ctx: ScenarioContext) -> dict[str, Any]:
    if not isinstance(ctx.data, dict):
        ctx.data = {}
    return ctx.data


def _repo(ctx: ScenarioContext) -> StoreRepository:
    state = _state(ctx)
    if "repo" not in state:
        state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))
    return state["repo"]


def _ingest(ctx: ScenarioContext, csv_text: str) -> None:
    (record,) = _repo(ctx).ingest("sales.csv", csv_text.encode())
    state = _state(ctx)
    state["dataset"] = record.name
    state["raw_counts"] = _repo(ctx).store.value_counts(
        record.name, state.get("column", "region")
    )


def _quoted(text: str) -> list[str]:
    return re.findall(r'"([^"]*)"', text)


def _restart(ctx: ScenarioContext) -> StoreRepository:
    """Rebuild the repository over the same data dir — production boot."""
    state = _state(ctx)
    state["repo"] = StoreRepository(str(ctx.tmp_path / "data"))
    return state["repo"]


def _totals(ctx: ScenarioContext) -> dict[str, float]:
    state = _state(ctx)
    out: dict[str, float] = {}
    for region, amount in state["repo"].store.fetch_all(state["dataset"]):
        out[region] = out.get(region, 0) + float(amount)
    return out


# --------------------------------------------------------------------------- #
# Givens — fixture files built from the step text
# --------------------------------------------------------------------------- #
@step(r'an ingested file whose "(?P<column>[^"]+)" column holds (?P<values>.+)')
def given_single_column_file(ctx: ScenarioContext, column: str, values: str) -> None:
    _state(ctx)["column"] = column
    rows = "\n".join(_quoted(values))
    _ingest(ctx, f"{column}\n{rows}\n")


@step(
    r'an ingested sales file where case variants of "East" carry amounts '
    r'10, 20 and 30 and "West" carries 40 and 50'
)
def given_sales_file(ctx: ScenarioContext) -> None:
    _state(ctx)["column"] = "region"
    _ingest(ctx, "region,amount\nEast,10\neast,20\nEAST,30\nWest,40\nWest,50\n")


@step(
    r'an ingested file where near-unique "order_id" values include the '
    r'case-colliding pair "A1" and "a1"'
)
def given_identifier_file(ctx: ScenarioContext) -> None:
    _state(ctx)["column"] = "order_id"
    extra = "\n".join(f"B{i},{i}" for i in range(3, 10))
    _ingest(ctx, f"order_id,amount\nA1,10\na1,20\nB2,30\n{extra}\n")


@step(r"the app runs offline with no AI features available")
def given_offline(ctx: ScenarioContext) -> None:
    os.environ.pop("ANALYST_CATALOG", None)
    os.environ.pop("ANALYST_CATALOG_CASSETTE", None)


@step(r'the proposed rule for column "(?P<column>[^"]+)" is approved')
def given_rule_approved(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    state["repo"].approve_normalization(state["dataset"], f"norm:{column}")


# --------------------------------------------------------------------------- #
# Whens
# --------------------------------------------------------------------------- #
@step(r"the user reviews the dataset's normalization findings")
def when_review_findings(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    proposals, applied = state["repo"].normalization(state["dataset"])
    state["proposals"], state["applied"] = proposals, applied


@step(
    r'the user queries the distinct values of "(?P<column>[^"]+)" '
    r"without approving anything"
)
def when_query_distinct_unapproved(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    state["counts"] = state["repo"].store.value_counts(state["dataset"], column)


@step(r'the user approves the proposed rule for column "(?P<column>[^"]+)"')
def when_approve(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    state["repo"].approve_normalization(state["dataset"], f"norm:{column}")


@step(r"the user asks for the total amount by region")
def when_totals(ctx: ScenarioContext) -> None:
    _state(ctx)["totals"] = _totals(ctx)


@step(r'the user revokes the approved rule for column "(?P<column>[^"]+)"')
def when_revoke(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    state["repo"].revoke_normalization(state["dataset"], f"norm:{column}")


@step(r'the user dismisses the proposal for column "(?P<column>[^"]+)"')
def when_dismiss(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    state["repo"].dismiss_normalization(state["dataset"], f"norm:{column}")


@step(r"the dataset is profiled again")
def when_profiled_again(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    state["repo"].store.profile(state["dataset"])
    proposals, applied = state["repo"].normalization(state["dataset"])
    state["proposals"], state["applied"] = proposals, applied


@step(r"the app restarts")
def when_app_restarts(ctx: ScenarioContext) -> None:
    _restart(ctx)


@step(r"the user approves a proposal that does not exist")
def when_approve_missing(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    try:
        state["repo"].approve_normalization(state["dataset"], "norm:no-such-column")
        state["error"] = None
    except UnknownNormalizationError as exc:
        state["error"] = exc


# --------------------------------------------------------------------------- #
# Thens — detection
# --------------------------------------------------------------------------- #
@step(
    r'a finding for column "(?P<column>[^"]+)" groups the case variants '
    r"(?P<values>.+)"
)
def then_case_variants_grouped(ctx: ScenarioContext, column: str, values: str) -> None:
    state = _state(ctx)
    rule = next((r for r in state["proposals"] if r.column == column), None)
    assert rule is not None, f"no finding for column {column!r}"
    grouped = {v.value for g in rule.groups for v in g.variants}
    expected = set(_quoted(values))
    assert expected <= grouped, f"expected variants {expected}, got {grouped}"
    state["finding"] = rule


@step(r"each variant in the finding carries its row count")
def then_variant_row_counts(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    raw = state["raw_counts"]
    for group in state["finding"].groups:
        for variant in group.variants:
            assert variant.rows == raw[variant.value], (
                f"{variant.value!r}: reported {variant.rows}, "
                f"ingested {raw[variant.value]}"
            )


@step(
    r'a finding for column "(?P<column>[^"]+)" groups the whitespace variants '
    r'of "(?P<value>[^"]+)"'
)
def then_whitespace_grouped(ctx: ScenarioContext, column: str, value: str) -> None:
    state = _state(ctx)
    rule = next((r for r in state["proposals"] if r.column == column), None)
    assert rule is not None, f"no finding for column {column!r}"
    group = next((g for g in rule.groups if g.canonical == value), None)
    assert group is not None, f"no group standardizing on {value!r}"
    assert len(group.variants) >= 2


@step(r"no normalization is proposed")
def then_nothing_proposed(ctx: ScenarioContext) -> None:
    assert _state(ctx)["proposals"] == []


@step(
    r'the proposal for column "(?P<column>[^"]+)" describes merging '
    r'(?P<n>\d+) variants into "(?P<canonical>[^"]+)"'
)
def then_proposal_describes(
    ctx: ScenarioContext, column: str, n: str, canonical: str
) -> None:
    state = _state(ctx)
    rule = next((r for r in state["proposals"] if r.column == column), None)
    assert rule is not None, f"no proposal for column {column!r}"
    assert f'{n} variants into "{canonical}"' in rule.description, rule.description


@step(r'no proposal targets column "(?P<column>[^"]+)"')
def then_no_proposal_for(ctx: ScenarioContext, column: str) -> None:
    offenders = [r.column for r in _state(ctx)["proposals"] if r.column == column]
    assert not offenders, f"unexpected proposal for {column!r}"


# --------------------------------------------------------------------------- #
# Thens — lifecycle
# --------------------------------------------------------------------------- #
@step(r'the values "East", "east", "EAST" and "West" appear exactly as ingested')
def then_values_as_ingested(ctx: ScenarioContext) -> None:
    counts = _state(ctx)["counts"]
    assert set(counts) == {"East", "east", "EAST", "West"}


@step(
    r'the totals show "(?P<a>[^"]+)" at (?P<a_total>\d+) '
    r'and "(?P<b>[^"]+)" at (?P<b_total>\d+)'
)
def then_totals_show(
    ctx: ScenarioContext, a: str, a_total: str, b: str, b_total: str
) -> None:
    totals = _state(ctx)["totals"]
    assert totals.get(a) == float(a_total), totals
    assert totals.get(b) == float(b_total), totals
    assert set(totals) == {a, b}, f"unexpected extra groups: {totals}"


@step(
    r'the distinct values of "(?P<column>[^"]+)" are '
    r'"East", "east", "EAST" and "West" again'
)
def then_distinct_restored(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    counts = state["repo"].store.value_counts(state["dataset"], column)
    assert set(counts) == {"East", "east", "EAST", "West"}


@step(r'no proposal for column "(?P<column>[^"]+)" is offered')
def then_no_proposal_offered(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    proposals, _ = state["repo"].normalization(state["dataset"])
    assert all(r.column != column for r in proposals)


@step(r'after the app restarts no proposal for column "(?P<column>[^"]+)" is offered')
def then_no_proposal_after_restart(ctx: ScenarioContext, column: str) -> None:
    repo = _restart(ctx)
    proposals, _ = repo.normalization(_state(ctx)["dataset"])
    assert all(r.column != column for r in proposals)


@step(r'the "(?P<column>[^"]+)" column\'s profile counts (?P<n>\d+) distinct values')
def then_profile_distinct(ctx: ScenarioContext, column: str, n: str) -> None:
    state = _state(ctx)
    record = state["repo"].get_dataset(state["dataset"])
    col = next(c for c in record.summary.profile.columns if c.name == column)
    assert col.distinct_count == int(n), f"distinct={col.distinct_count}"


@step(r'the profile\'s example values include "East" and no other case variant of it')
def then_profile_examples_standardized(ctx: ScenarioContext) -> None:
    state = _state(ctx)
    record = state["repo"].get_dataset(state["dataset"])
    col = next(c for c in record.summary.profile.columns if c.name == "region")
    samples = {str(s) for s in col.samples}
    assert "East" in samples, samples
    assert not ({"east", "EAST"} & samples), samples


@step(r'the total amount by region still shows "East" at (?P<total>\d+)')
def then_totals_after_restart(ctx: ScenarioContext, total: str) -> None:
    totals = _totals(ctx)
    assert totals.get("East") == float(total), totals


@step(r"the action is rejected as not found")
def then_rejected_not_found(ctx: ScenarioContext) -> None:
    assert isinstance(_state(ctx)["error"], UnknownNormalizationError)


@step(r'the distinct values of "(?P<column>[^"]+)" are unchanged')
def then_distinct_unchanged(ctx: ScenarioContext, column: str) -> None:
    state = _state(ctx)
    counts = state["repo"].store.value_counts(state["dataset"], column)
    assert counts == state["raw_counts"]


# --------------------------------------------------------------------------- #
# Workbench flow (AC-11) — Playwright against the fixtures app
# --------------------------------------------------------------------------- #
@step(r"the analyst app is open in a browser")
def given_app_open(ctx: ScenarioContext) -> None:
    expect = _expect()
    ctx.page.goto(_STACK["web"])
    expect(ctx.page.get_by_text("Catalog", exact=True).first).to_be_visible()
    # Pin "no page reload": this marker must survive every workbench action.
    ctx.page.evaluate("window.__no_reload_pin = 1")


@step(r"the user opens the sample sales table in the workbench")
def when_open_sales_table(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Open table sales").first.click()


@step(r'the column "(?P<column>[^"]+)" visibly indicates a pending proposal')
def then_column_indicates_proposal(ctx: ScenarioContext, column: str) -> None:
    expect = _expect()
    expect(
        ctx.page.get_by_label(f"Normalization proposal pending for {column}")
    ).to_be_visible()


@step(r'the user opens the column "(?P<column>[^"]+)"')
def when_open_column(ctx: ScenarioContext, column: str) -> None:
    _state(ctx)["ui_column"] = column
    ctx.page.get_by_role("button", name=f"Column {column}").click()


@step(r"the proposal is visible with its variants")
def then_proposal_visible(ctx: ScenarioContext) -> None:
    expect = _expect()
    card = ctx.page.get_by_label(
        f"Normalization proposal for {_state(ctx)['ui_column']}"
    )
    expect(card).to_be_visible()
    expect(card.get_by_text('"east"', exact=False).first).to_be_visible()
    expect(card.get_by_text('"EAST"', exact=False).first).to_be_visible()


@step(r"the user approves the proposal in the workbench")
def when_approve_in_workbench(ctx: ScenarioContext) -> None:
    ctx.page.get_by_role("button", name="Approve normalization proposal").click()


@step(r"the workbench shows the proposal as applied without a page reload")
def then_shows_applied_no_reload(ctx: ScenarioContext) -> None:
    expect = _expect()
    expect(
        ctx.page.get_by_label(f"Applied normalization for {_state(ctx)['ui_column']}")
    ).to_be_visible()
    assert ctx.page.evaluate("window.__no_reload_pin") == 1, "the page reloaded"


@step(r'the user opens the column "(?P<column>[^"]+)" of the sample sales table')
def when_open_column_of_sales(ctx: ScenarioContext, column: str) -> None:
    _state(ctx)["ui_column"] = column
    ctx.page.get_by_role("button", name="Open table sales").first.click()
    ctx.page.get_by_role("button", name=f"Column {column}").click()


@step(r"the user dismisses its normalization proposal")
def when_dismiss_in_workbench(ctx: ScenarioContext) -> None:
    expect = _expect()
    column = _state(ctx)["ui_column"]
    expect(
        ctx.page.get_by_label(f"Normalization proposal for {column}")
    ).to_be_visible()
    ctx.page.get_by_role("button", name="Dismiss normalization proposal").click()


@step(r"no normalization proposal remains on the column")
def then_no_proposal_remains(ctx: ScenarioContext) -> None:
    expect = _expect()
    column = _state(ctx)["ui_column"]
    expect(ctx.page.get_by_label(f"Normalization proposal for {column}")).to_have_count(
        0
    )
    expect(
        ctx.page.get_by_label(f"Normalization proposal pending for {column}")
    ).to_have_count(0)
