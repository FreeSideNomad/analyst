"""Feature 013 — normalization domain policy + engine detection.

Domain: canonical keys, canonical-value choice, variant grouping, rule
rendering — pure and deterministic. Engine: detect() over a real DuckDB
store, candidate gating by profile (text-typed, non-identifier).
"""

from __future__ import annotations

import pytest

from analyst.domain.normalization import (
    NormalizationRule,
    Variant,
    canonical_key,
    choose_canonical,
    group_variants,
    rule_for,
)


# --------------------------------------------------------------------------- #
# canonical_key — trim + collapse internal whitespace + casefold
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("East", "east"),
        ("EAST", "east"),
        (" East", "east"),
        ("New  York", "new york"),
        ("  New   York  ", "new york"),
        ("Straße", "strasse"),  # unicode casefold, not lower()
    ],
)
def test_canonical_key_normalizes_case_and_whitespace(raw, key):
    assert canonical_key(raw) == key


def test_canonical_key_keeps_distinct_values_distinct():
    assert canonical_key("East") != canonical_key("West")


# --------------------------------------------------------------------------- #
# choose_canonical — most rows, then clean form, then title-case, then lex
# --------------------------------------------------------------------------- #
def test_most_frequent_variant_wins():
    variants = (Variant("EAST", 10), Variant("East", 3), Variant("east", 1))
    assert choose_canonical(variants) == "EAST"


def test_tie_prefers_the_clean_form_over_padded_ones():
    variants = (
        Variant(" New York", 2),
        Variant("New York", 2),
        Variant("New  York", 2),
    )
    assert choose_canonical(variants) == "New York"


def test_tie_among_clean_forms_prefers_title_case():
    variants = (Variant("east", 1), Variant("EAST", 1), Variant("East", 1))
    assert choose_canonical(variants) == "East"


def test_tie_without_title_case_falls_back_lexicographic():
    variants = (Variant("iOS", 1), Variant("IOS", 1))
    assert choose_canonical(variants) == "IOS"


def test_canonical_is_always_an_observed_variant():
    variants = (Variant("EAST", 5), Variant("east", 5))
    assert choose_canonical(variants) in {"EAST", "east"}


# --------------------------------------------------------------------------- #
# group_variants — only real collisions become groups
# --------------------------------------------------------------------------- #
def test_grouping_collects_only_colliding_values():
    counts = {"East": 1, "east": 1, "EAST": 1, "West": 2}
    groups = group_variants(counts)
    assert len(groups) == 1
    (group,) = groups
    assert group.canonical == "East"
    assert {v.value: v.rows for v in group.variants} == {
        "East": 1,
        "east": 1,
        "EAST": 1,
    }


def test_clean_counts_produce_no_groups():
    assert group_variants({"East": 2, "West": 1}) == ()


def test_whitespace_variants_group_together():
    counts = {"New York": 1, " New York": 1, "New  York": 1, "Boston": 1}
    (group,) = group_variants(counts)
    assert group.canonical == "New York"
    assert len(group.variants) == 3


# --------------------------------------------------------------------------- #
# rule_for — explicit frozen mapping + plain-language description
# --------------------------------------------------------------------------- #
def test_rule_mapping_covers_only_non_canonical_variants():
    counts = {"East": 1, "east": 1, "EAST": 1, "West": 2}
    rule = rule_for("region", group_variants(counts))
    assert isinstance(rule, NormalizationRule)
    assert rule.rule_id == "norm:region"
    assert rule.column == "region"
    assert rule.mapping == {"east": "East", "EAST": "East"}


def test_rule_description_names_the_merge_in_plain_language():
    counts = {"East": 1, "east": 1, "EAST": 1}
    rule = rule_for("region", group_variants(counts))
    assert "3 variants" in rule.description
    assert '"East"' in rule.description
    assert "region" in rule.description


def test_rule_description_covers_multiple_groups():
    counts = {"East": 1, "east": 1, "West": 1, "WEST": 1, "west": 1}
    rule = rule_for("region", group_variants(counts))
    assert "2 variants" in rule.description and "3 variants" in rule.description


# --------------------------------------------------------------------------- #
# Engine detection over a real store
# --------------------------------------------------------------------------- #
from analyst.engine.normalization import detect  # noqa: E402
from analyst.engine.store import DatasetStore  # noqa: E402


def _store_with(tmp_path, name: str, csv_text: str) -> DatasetStore:
    src = tmp_path / f"{name}.src.csv"
    src.write_text(csv_text)
    store = DatasetStore(tmp_path / "data")
    store.materialize_delimited(name, src)
    return store


def test_detect_finds_case_variants_with_row_counts(tmp_path):
    store = _store_with(
        tmp_path,
        "sales",
        "region,amount\nEast,10\neast,20\nEAST,30\nWest,40\nWest,50\n",
    )
    (rule,) = detect(store, "sales", store.profile("sales"))
    assert rule.column == "region"
    (group,) = rule.groups
    assert {v.value: v.rows for v in group.variants} == {
        "East": 1,
        "east": 1,
        "EAST": 1,
    }


def test_detect_is_quiet_on_clean_data(tmp_path):
    store = _store_with(tmp_path, "clean", "region\nEast\nEast\nWest\n")
    assert detect(store, "clean", store.profile("clean")) == ()


def test_detect_exempts_near_unique_identifier_columns(tmp_path):
    rows = "\n".join(f"B{i},{i}" for i in range(3, 10))
    store = _store_with(tmp_path, "ids", f"order_id,amount\nA1,1\na1,2\nB2,3\n{rows}\n")
    rules = detect(store, "ids", store.profile("ids"))
    assert all(rule.column != "order_id" for rule in rules)


def test_detect_skips_non_text_columns(tmp_path):
    store = _store_with(tmp_path, "nums", "n,region\n1,East\n1,east\n2,West\n2,West\n")
    rules = detect(store, "nums", store.profile("nums"))
    assert [rule.column for rule in rules] == ["region"]


def test_detect_ignores_nulls(tmp_path):
    store = _store_with(
        tmp_path, "gaps", "region,x\nEast,1\neast,2\n,3\n,4\nWest,5\nWest,6\n"
    )
    (rule,) = detect(store, "gaps", store.profile("gaps"))
    assert all(v.value for group in rule.groups for v in group.variants)


# --------------------------------------------------------------------------- #
# Repository lifecycle: propose -> approve/dismiss/revoke, persist, refresh
# --------------------------------------------------------------------------- #
from analyst.api.repository import StoreRepository  # noqa: E402
from analyst.domain.normalization import UnknownNormalizationError  # noqa: E402

MESSY = "region,amount\nEast,10\neast,20\nEAST,30\nWest,40\nWest,50\n"


def _repo(tmp_path) -> StoreRepository:
    return StoreRepository(str(tmp_path / "data"))


def _ingest(repo, text=MESSY, name="sales.csv") -> str:
    (rec,) = repo.ingest(name, text.encode())
    return rec.name


def test_proposals_surface_through_the_repository(tmp_path):
    repo = _repo(tmp_path)
    name = _ingest(repo)
    proposals, applied = repo.normalization(name)
    assert [r.rule_id for r in proposals] == ["norm:region"]
    assert applied == []


def test_approval_standardizes_queries_and_profile(tmp_path):
    repo = _repo(tmp_path)
    name = _ingest(repo)
    repo.approve_normalization(name, "norm:region")
    assert repo.store.value_counts(name, "region") == {"East": 3, "West": 2}
    region = next(
        c for c in repo.get_dataset(name).summary.profile.columns if c.name == "region"
    )
    assert region.distinct_count == 2
    proposals, applied = repo.normalization(name)
    assert proposals == [] and [r.rule_id for r in applied] == ["norm:region"]


def test_approved_rule_survives_a_restart(tmp_path):
    name = _ingest(_repo(tmp_path))
    _repo(tmp_path).approve_normalization(name, "norm:region")
    reborn = _repo(tmp_path)
    assert reborn.store.value_counts(name, "region") == {"East": 3, "West": 2}
    proposals, applied = reborn.normalization(name)
    assert proposals == [] and [r.rule_id for r in applied] == ["norm:region"]


def test_acting_on_an_unknown_rule_fails_cleanly(tmp_path):
    repo = _repo(tmp_path)
    name = _ingest(repo)
    with pytest.raises(UnknownNormalizationError):
        repo.approve_normalization(name, "norm:nope")
    assert repo.store.value_counts(name, "region") == {
        "East": 1,
        "east": 1,
        "EAST": 1,
        "West": 2,
    }


def test_dismissal_is_remembered_across_restarts(tmp_path):
    repo = _repo(tmp_path)
    name = _ingest(repo)
    repo.dismiss_normalization(name, "norm:region")
    assert repo.normalization(name) == ([], [])
    assert _repo(tmp_path).normalization(name) == ([], [])
    # ...and the data was never touched
    assert repo.store.value_counts(name, "region")["EAST"] == 1


def test_revoke_restores_raw_values_and_reproposes(tmp_path):
    repo = _repo(tmp_path)
    name = _ingest(repo)
    repo.approve_normalization(name, "norm:region")
    repo.revoke_normalization(name, "norm:region")
    assert repo.store.value_counts(name, "region") == {
        "East": 1,
        "east": 1,
        "EAST": 1,
        "West": 2,
    }
    proposals, applied = repo.normalization(name)
    assert [r.rule_id for r in proposals] == ["norm:region"] and applied == []


def test_refresh_reapplies_the_approved_rule(tmp_path):
    repo = _repo(tmp_path)
    name = _ingest(repo)
    repo.approve_normalization(name, "norm:region")
    repo.refresh(name, "sales.csv", b"region,amount\nEast,1\neast,2\nWest,3\n")
    assert repo.store.value_counts(name, "region") == {"East": 2, "West": 1}


# --------------------------------------------------------------------------- #
# API routes: GET state, approve/dismiss/revoke, 404 on unknown rule
# --------------------------------------------------------------------------- #
from fastapi.testclient import TestClient  # noqa: E402

from analyst.api.app import create_app  # noqa: E402
from analyst.api.repository import FixtureRepository  # noqa: E402


def _client_with_messy(tmp_path) -> tuple[TestClient, str]:
    repo = _repo(tmp_path)
    name = _ingest(repo)
    return TestClient(create_app(repo)), name


def test_get_normalization_state(tmp_path):
    client, name = _client_with_messy(tmp_path)
    body = client.get(f"/api/datasets/{name}/normalization").json()
    (proposal,) = body["proposals"]
    assert proposal["ruleId"] == "norm:region"
    assert proposal["column"] == "region"
    assert "3 variants" in proposal["description"]
    (group,) = proposal["groups"]
    assert group["canonical"] == "East"
    assert {v["value"]: v["rows"] for v in group["variants"]} == {
        "East": 1,
        "east": 1,
        "EAST": 1,
    }
    assert body["applied"] == []


def test_approve_route_applies_and_returns_new_state(tmp_path):
    client, name = _client_with_messy(tmp_path)
    body = client.post(f"/api/datasets/{name}/normalization/norm:region/approve").json()
    assert body["proposals"] == []
    assert [r["ruleId"] for r in body["applied"]] == ["norm:region"]


def test_unknown_rule_is_a_clean_404(tmp_path):
    client, name = _client_with_messy(tmp_path)
    for action in ("approve", "dismiss", "revoke"):
        response = client.post(
            f"/api/datasets/{name}/normalization/norm:ghost/{action}"
        )
        assert response.status_code == 404, action
        assert "norm:ghost" in response.json()["detail"]


def test_unknown_dataset_is_a_404_too(tmp_path):
    client, _ = _client_with_messy(tmp_path)
    assert client.get("/api/datasets/nope/normalization").status_code == 404


def test_fixture_repo_seeds_a_proposal_on_sales_region():
    client = TestClient(create_app(FixtureRepository()))
    body = client.get("/api/datasets/sales/normalization").json()
    (proposal,) = body["proposals"]
    assert proposal["column"] == "billing_region"
    body = client.post(
        "/api/datasets/sales/normalization/norm:billing_region/approve"
    ).json()
    assert body["proposals"] == [] and len(body["applied"]) == 1


def test_fixture_repo_dismiss_removes_the_proposal():
    client = TestClient(create_app(FixtureRepository()))
    body = client.post(
        "/api/datasets/sales/normalization/norm:billing_region/dismiss"
    ).json()
    assert body["proposals"] == [] and body["applied"] == []
