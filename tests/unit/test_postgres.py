import pytest

from yia.docker import postgres_data_path, postgres_environment


@pytest.mark.parametrize(
    ("version", "target"),
    [
        ("17", "/var/lib/postgresql/data"),
        ("17.9-alpine", "/var/lib/postgresql/data"),
        ("18", "/var/lib/postgresql"),
        ("18.1-alpine", "/var/lib/postgresql"),
        ("19beta3", "/var/lib/postgresql"),
    ],
)
def test_data_path_follows_official_image_layout(
    version: str,
    target: str,
) -> None:
    assert postgres_data_path(version) == target


def test_environment_references_dotenv_without_embedding_secrets() -> None:
    environment = postgres_environment()

    assert environment == {
        "POSTGRES_DB": "${POSTGRES_DB:-postgres}",
        "POSTGRES_PASSWORD": (
            "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}"
        ),
        "POSTGRES_USER": "${POSTGRES_USER:-postgres}",
    }
    assert all("password=" not in value.lower() for value in environment.values())


def test_data_path_rejects_a_version_without_leading_major() -> None:
    with pytest.raises(ValueError, match="must begin with its major number"):
        postgres_data_path("latest")
