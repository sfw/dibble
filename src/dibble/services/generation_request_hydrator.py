from __future__ import annotations

from dibble.models.generation import GenerationRequest, TargetKcGenerationHint
from dibble.services.protocols import KnowledgeComponentStore


def hydrate_target_kc_hints(
    *,
    request: GenerationRequest,
    knowledge_component_store: KnowledgeComponentStore | None,
) -> GenerationRequest:
    if knowledge_component_store is None or request.target_kc_hints or not request.target_kc_ids:
        return request

    hints: list[TargetKcGenerationHint] = []
    for kc_id in dict.fromkeys(request.target_kc_ids):
        component = knowledge_component_store.get(kc_id)
        if component is None:
            continue

        nearby_names = [
            nearby_component.name
            for nearby_kc_id in component.nearby_kc_ids[:2]
            if (nearby_component := knowledge_component_store.get(nearby_kc_id)) is not None
        ]
        misconceptions = component.common_misconceptions[:2]
        hints.append(
            TargetKcGenerationHint(
                kc_id=component.kc_id,
                kc_name=component.name,
                concept_family=component.concept_family,
                taxonomy_cluster_id=component.taxonomy_cluster_id,
                nearby_kc_names=nearby_names,
                misconception_ids=[item.misconception_id for item in misconceptions],
                misconception_labels=[item.label for item in misconceptions],
                misconception_descriptions=[item.description for item in misconceptions],
                remediation_hints=[item.remediation_hint for item in misconceptions if item.remediation_hint is not None],
            )
        )

    if not hints:
        return request
    return request.model_copy(update={"target_kc_hints": hints})
