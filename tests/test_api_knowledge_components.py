from tests.support import build_knowledge_component


def test_knowledge_component_round_trip_and_prerequisites(client):
    client.put(
        "/api/knowledge-components/KC-1",
        json=build_knowledge_component("KC-1", name="Identify numerator and denominator"),
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
    assert [item["kc_id"] for item in prerequisites_response.json()] == ["KC-1"]
