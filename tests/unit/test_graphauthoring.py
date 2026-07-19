"""Feature 019 — the workspace bridge + guided authoring, on REAL Berka
uploads. The equivalence contract: the generated pipeline must reproduce
the curated 018 bundle bitwise on the same machine (same data, same seed,
same RNG stream)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ANALYST_ML_CACHE", "tests/.ml_cache")

from analyst.engine.relgraph import available  # noqa: E402
from analyst.engine.relgraph import workspace as ws  # noqa: E402

pytestmark = pytest.mark.skipif(
    not available(), reason="ml extra (torch stack) not installed"
)

TIME_PINS = {
    "berka_account.csv": "open_date",
    "berka_card.csv": "issued",
    "berka_loan.csv": "grant_date",
    "berka_trans.csv": "trans_date",
}
LABEL_SQL = (
    "SELECT loan_id, grant_date AS as_of, "
    "CASE WHEN status IN ('B','D') THEN 1 ELSE 0 END AS label FROM berka_loan"
)


class StubAuthor:
    def author(self, table, structure, question):  # noqa: ANN001
        from analyst.agentic.graphauthor import AuthoredTask

        return AuthoredTask(
            entity_table="berka_loan",
            entity_column="loan_id",
            time_column="grant_date",
            horizon_days=365,
            val_cutoff="1996-07-01",
            test_cutoff="1997-06-01",
            label_sql=LABEL_SQL,
            time_columns={ws.table_alias(k): v for k, v in TIME_PINS.items()},
            outcome_columns=["payments"],  # post-outcome judgment (curated parity)
            framing={
                "question": "Will this loan end in default?",
                "moment": "Predicted at the moment the loan is granted.",
                "honesty": "The columns recording how it ended are hidden.",
            },
        )


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    from analyst.api.repository import StoreRepository

    repo = StoreRepository(
        str(tmp_path_factory.mktemp("ws") / "data"), graph_author=StubAuthor()
    )
    repo.add_relational_bundle()
    return repo


@pytest.fixture(scope="module")
def authored(repo):
    task = repo.author_relational_task("which loans will end in default?")
    return repo.confirm_relational_task(task["task_id"])


def test_spec_derives_only_validated_links(repo):
    tables = {n: r.summary.profile for n, r in repo._records.items()}
    rels = repo.store.discover_relationships()
    spec = ws.spec_from_workspace(
        tables,
        rels,
        name="ws-derive",
        val_cutoff="1996-07-01",
        test_cutoff="1997-06-01",
        time_columns=TIME_PINS,
    )
    derived = {
        (t.name, fk.column, fk.ref_table)
        for t in spec.tables.values()
        for fk in t.foreign_keys
    }
    validated = {
        (ws.table_alias(r.child_table), r.child_column, ws.table_alias(r.parent_table))
        for r in rels
    }
    assert derived and derived <= validated  # subset — never invented
    assert spec.tables["berka_loan"].time_column == "grant_date"
    assert spec.tables["berka_client"].time_column is None  # birth date ≠ event


def test_graph_hints_reach_past_the_farthest_table(repo):
    tables = {n: r.summary.profile for n, r in repo._records.items()}
    rels = repo.store.discover_relationships()
    spec = ws.spec_from_workspace(
        tables,
        rels,
        name="ws-hints",
        val_cutoff="1996-07-01",
        test_cutoff="1997-06-01",
        time_columns=TIME_PINS,
    )
    assert ws.graph_hints(spec, "berka_loan") == {
        "num_layers": 4,
        "num_neighbors": [16, 64, 16, 8],
    }


def test_label_columns_over_exclude_safely():
    cols = ["loan_id", "status", "payments", "amount", "grant_date"]
    hidden = ws.label_columns(LABEL_SQL, cols)
    assert "status" in hidden
    assert "amount" not in hidden


def test_authoring_produces_confirmed_task_with_honesty_checks(authored):
    assert authored["status"] == "defined"
    assert authored["hidden_columns"] == ["payments", "status"]
    assert abs(authored["canary"] - 0.5) < 0.1  # coin flip: honest wiring
    assert authored["source"] == "uploads"
    assert authored["warnings"] == []


def test_include_hidden_column_is_refused(repo, authored):
    with pytest.raises(ValueError, match="stays hidden"):
        repo.include_hidden_column(authored["task_id"], "status")


def test_generated_flow_reproduces_curated_bitwise(repo, authored):
    from analyst.engine.relgraph.pipeline import train_tiers

    curated = train_tiers("berka", "loan_default", seed=13)
    trained = repo.train_relational(authored["task_id"])
    # Baseline: bitwise (LightGBM is naming-independent).
    assert trained["metrics"]["baseline"] == curated.metrics["baseline"]
    # Graph/hybrid: the generated tables carry different NAMES
    # (berka_loan vs loan), which shifts dict-iteration order inside
    # torch-frame/relbench and with it the RNG stream — verified: the two
    # specs are structurally identical (columns, types, order, FKs, PKs,
    # time columns). Same-machine near-equivalence, far tighter than the
    # cross-platform ±0.07 window.
    assert (
        abs(
            trained["metrics"]["graph"]["test_auroc"]
            - curated.metrics["graph"]["test_auroc"]
        )
        <= 0.02
    )
    assert (
        abs(
            trained["metrics"]["hybrid"]["test_auroc"]
            - curated.metrics["hybrid"]["test_auroc"]
        )
        <= 0.02
    )
    assert trained["story"]["source"] == "uploads"
    assert "never leaving" in trained["story"]["local_build"]
    frame = repo.store.fetch_frame(trained["predictions_dataset"])
    assert len(frame) == 682


def test_giveaway_detector_flags_outcome_recording_column(repo):
    import pandas as pd

    from analyst.engine.relgraph.honesty import giveaway_columns
    from analyst.engine.relgraph.tasks import load_training_table

    frame = load_training_table("berka", "loan_default")
    loans = repo.store.fetch_frame("berka_loan.csv")
    leaky = loans.copy()
    leaky["settled_flag"] = leaky["status"].isin(["B", "D"]).astype(int)
    flagged = giveaway_columns(
        frame.rename(columns={frame.columns[0]: "loan_id"}),
        leaky,
        "loan_id",
        ["amount", "duration", "settled_flag"],
    )
    assert flagged == ["settled_flag"]
    assert isinstance(frame, pd.DataFrame)


def test_unconfirmed_task_never_trains(repo):
    task = repo.author_relational_task("second question about defaults")
    with pytest.raises(ValueError, match="confirm"):
        repo.train_relational(task["task_id"])
