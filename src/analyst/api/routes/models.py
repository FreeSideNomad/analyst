"""Model routes — feature 012.

Task dictionaries cross the wire as stored (snake_case registry records);
the guidance/training errors map to the established codes. The trainer only
ever runs server-side committed code.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from analyst.api.deps import get_repository
from analyst.api.repository import DatasetRepository
from analyst.api.routes.datasets import to_dataset_schema
from analyst.api.schemas import Camel
from analyst.domain.models import UnknownModelError

router = APIRouter(prefix="/api")


class NewTaskRequest(Camel):
    dataset: str
    target: str


class FeaturesRequest(Camel):
    accepted: list[str]


class TrainRequest(Camel):
    params: dict = {}


def _guard(call):  # noqa: ANN001, ANN202
    from analyst.agentic.graphauthor import GraphAuthoringError
    from analyst.agentic.models import ModelGuidanceError
    from analyst.engine.mltrain import LeakageError
    from analyst.engine.relgraph.errors import RelgraphError

    try:
        return call()
    except UnknownModelError as exc:
        raise HTTPException(404, f"No such model: {exc}") from None
    except KeyError as exc:
        raise HTTPException(404, f"No such dataset: {exc}") from None
    except (ValueError, LeakageError) as exc:
        raise HTTPException(400, str(exc)) from None
    except (ModelGuidanceError, GraphAuthoringError) as exc:
        raise HTTPException(502, str(exc)) from None
    except RelgraphError as exc:
        raise HTTPException(
            502, f"Training failed and nothing was saved: {exc}"
        ) from None


@router.get("/models/gallery")
def gallery(repo: DatasetRepository = Depends(get_repository)) -> dict:
    return {
        "samples": [
            {
                "key": s.key,
                "title": s.title,
                "target": s.target,
                "description": s.description,
            }
            for s in repo.model_gallery()
        ]
    }


@router.post("/models/gallery/{key}")
def add_sample(key: str, repo: DatasetRepository = Depends(get_repository)) -> dict:
    from analyst.engine.mlsamples import UnknownSampleError

    from typing import cast

    from analyst.api.repository import DatasetRecord

    try:
        record = repo.add_sample(key)
    except UnknownSampleError as exc:
        raise HTTPException(404, f"No such sample: {exc}") from None
    return to_dataset_schema(cast(DatasetRecord, record)).dump()


@router.post("/models/tasks")
def create_task(
    body: NewTaskRequest, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    return _guard(lambda: repo.create_model_task(body.dataset, body.target))


@router.patch("/models/tasks/{task_id}/features")
def update_features(
    task_id: str,
    body: FeaturesRequest,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    return _guard(lambda: repo.update_task_features(task_id, body.accepted))


@router.post("/models/tasks/{task_id}/train")
def train(
    task_id: str,
    body: TrainRequest,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    return _guard(lambda: repo.train_model(task_id, body.params or None))


@router.get("/models")
def list_models(repo: DatasetRepository = Depends(get_repository)) -> dict:
    return {"models": repo.models()}


# Feature 018 — relational graph models. Declared before the {task_id}
# routes so "relational" never matches as a task id.


class RelationalTaskRequest(Camel):
    task: str


@router.get("/models/relational")
def relational_bundle(repo: DatasetRepository = Depends(get_repository)) -> dict:
    return repo.relational_bundle()


@router.post("/models/relational/bundle")
def add_relational_bundle(
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    return _guard(repo.add_relational_bundle)


@router.post("/models/relational/tasks")
def create_relational_task(
    body: RelationalTaskRequest, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    return _guard(lambda: repo.create_relational_task(body.task))


@router.post("/models/relational/tasks/{task_id}/train")
def train_relational(
    task_id: str, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    return _guard(lambda: repo.train_relational(task_id))


# Feature 019 — guided authoring on the user's own linked data.


class AuthorRequest(Camel):
    question: str


class IncludeColumnRequest(Camel):
    column: str


@router.post("/models/relational/author")
def author_relational(
    body: AuthorRequest, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    return _guard(lambda: repo.author_relational_task(body.question))


@router.post("/models/relational/tasks/{task_id}/confirm")
def confirm_relational(
    task_id: str, repo: DatasetRepository = Depends(get_repository)
) -> dict:
    return _guard(lambda: repo.confirm_relational_task(task_id))


@router.post("/models/relational/tasks/{task_id}/include-column")
def include_hidden_column(
    task_id: str,
    body: IncludeColumnRequest,
    repo: DatasetRepository = Depends(get_repository),
) -> dict:
    return _guard(lambda: repo.include_hidden_column(task_id, body.column))


@router.get("/models/{task_id}")
def get_model(task_id: str, repo: DatasetRepository = Depends(get_repository)) -> dict:
    return _guard(lambda: repo.model(task_id))


@router.delete("/models/{task_id}", status_code=204)
def delete_model(
    task_id: str, repo: DatasetRepository = Depends(get_repository)
) -> None:
    _guard(lambda: repo.delete_model(task_id))
