from .apache import APACHE_VHOSTS_PATH, ApacheGenerator
from .compose import COMPOSE_PATH, ComposeGenerator
from .node import SUPPORTED_NODE_VERSIONS
from .php import PhpGenerator
from .postgres import (
    POSTGRES_CONTAINER_PORT,
    POSTGRES_DATA_VOLUME,
    POSTGRES_DEFAULT_DATABASE,
    POSTGRES_DEFAULT_USER,
    POSTGRES_SERVICE_NAME,
    postgres_data_path,
    postgres_environment,
)


def docker_generators() -> tuple[ApacheGenerator, PhpGenerator, ComposeGenerator]:
    return ApacheGenerator(), PhpGenerator(), ComposeGenerator()

__all__ = [
    "APACHE_VHOSTS_PATH",
    "ApacheGenerator",
    "COMPOSE_PATH",
    "ComposeGenerator",
    "PhpGenerator",
    "POSTGRES_CONTAINER_PORT",
    "POSTGRES_DATA_VOLUME",
    "POSTGRES_DEFAULT_DATABASE",
    "POSTGRES_DEFAULT_USER",
    "POSTGRES_SERVICE_NAME",
    "SUPPORTED_NODE_VERSIONS",
    "docker_generators",
    "postgres_data_path",
    "postgres_environment",
]
