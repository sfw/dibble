from __future__ import annotations

import json
import sqlite3
from uuid import UUID

from dibble.models.generation import ModalityRoutingPrior


class SQLiteModalityRoutingPriorStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, prior: ModalityRoutingPrior) -> ModalityRoutingPrior:
        self._conn.execute(
            """
            INSERT INTO modality_routing_priors(
                learner_id,
                scope,
                prior_key,
                context_key,
                payload,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(learner_id, scope, prior_key, context_key) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                str(prior.learner_id),
                prior.scope.value,
                prior.prior_key,
                prior.context_key,
                prior.model_dump_json(),
                prior.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return prior

    def get(
        self,
        *,
        learner_id: UUID,
        scope: str,
        prior_key: str,
        context_key: str,
    ) -> ModalityRoutingPrior | None:
        row = self._conn.execute(
            """
            SELECT payload FROM modality_routing_priors
            WHERE learner_id = ? AND scope = ? AND prior_key = ? AND context_key = ?
            """,
            (str(learner_id), scope, prior_key, context_key),
        ).fetchone()
        if row is None:
            return None
        return ModalityRoutingPrior.model_validate(json.loads(str(row[0])))

    def list_for_learner(self, *, learner_id: UUID) -> list[ModalityRoutingPrior]:
        rows = self._conn.execute(
            """
            SELECT payload FROM modality_routing_priors
            WHERE learner_id = ?
            ORDER BY updated_at DESC, scope ASC, prior_key ASC, context_key ASC
            """,
            (str(learner_id),),
        ).fetchall()
        return [
            ModalityRoutingPrior.model_validate(json.loads(str(payload)))
            for (payload,) in rows
        ]
