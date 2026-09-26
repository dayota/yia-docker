from .apache import APACHE_VHOSTS_PATH, ApacheGenerator
from .compose import COMPOSE_PATH, ComposeGenerator


def docker_generators() -> tuple[ApacheGenerator, ComposeGenerator]:
    return ApacheGenerator(), ComposeGenerator()

__all__ = [
    "APACHE_VHOSTS_PATH",
    "ApacheGenerator",
    "COMPOSE_PATH",
    "ComposeGenerator",
    "docker_generators",
]
