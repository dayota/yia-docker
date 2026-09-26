from .apache import APACHE_VHOSTS_PATH, ApacheGenerator
from .compose import COMPOSE_PATH, ComposeGenerator
from .node import SUPPORTED_NODE_VERSIONS
from .php import PhpGenerator


def docker_generators() -> tuple[ApacheGenerator, PhpGenerator, ComposeGenerator]:
    return ApacheGenerator(), PhpGenerator(), ComposeGenerator()

__all__ = [
    "APACHE_VHOSTS_PATH",
    "ApacheGenerator",
    "COMPOSE_PATH",
    "ComposeGenerator",
    "PhpGenerator",
    "SUPPORTED_NODE_VERSIONS",
    "docker_generators",
]
