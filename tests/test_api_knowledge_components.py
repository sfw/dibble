from tests.support import build_knowledge_component


def test_knowledge_component_round_trip_and_prerequisites(client):
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component(
            "KC-1",
            name="Identify numerator and denominator",
            common_misconceptions=[
                {
                    "misconception_id": "fraction-part-role-swap",
                    "label": "Swaps numerator and denominator roles",
                    "description": "The learner treats the numerator and denominator as interchangeable.",
                    "trigger_terms": ["numerator", "denominator", "swap"],
                    "remediation_hint": "Re-state what each number counts before comparing fractions.",
                }
            ],
        ),
    )
    client.put(
        "/api/knowledge-components/KC-2",
        json=build_knowledge_component(
            "KC-2",
            prerequisite_kc_ids=["KC-1"],
            name="Generate equivalent fractions",
        ),
    )

    list_response = client.get("/api/knowledge-components")
    prerequisites_response = client.get("/api/knowledge-components/KC-2/prerequisites")

    assert list_response.status_code == 200
    assert prerequisites_response.status_code == 200
    assert {item["kc_id"] for item in list_response.json()} == {"KC-1", "KC-2"}
    kc_one = next(item for item in list_response.json() if item["kc_id"] == "KC-1")
    assert kc_one["common_misconceptions"][0]["misconception_id"] == "fraction-part-role-swap"
    assert [item["kc_id"] for item in prerequisites_response.json()] == ["KC-1"]
