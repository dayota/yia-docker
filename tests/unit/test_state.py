from yia.state import YiaState


def test_state_serialization() -> None:
    state = YiaState.create(
        yia_version="0.1.0",
        schema_version=1,
        documentation_schema=1,
        configuration_hash="abc123",
    )
    payload = state.to_dict()
    assert payload["yia_version"] == "0.1.0"
    assert payload["schema_version"] == 1
    assert payload["documentation_schema"] == 1
    assert payload["configuration_hash"] == "abc123"
    assert payload["generated_at"]
