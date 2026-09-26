from .apache import APACHE_VHOSTS_PATH, ApacheGenerator
from .compose import COMPOSE_PATH, ComposeGenerator
from .php import PhpGenerator


def docker_generators() -> tuple[ApacheGenerator, PhpGenerator, ComposeGenerator]:
    return ApacheGenerator(), PhpGenerator(), ComposeGenerator()

__all__ = [
    "APACHE_VHOSTS_PATH",
    "ApacheGenerator",
    "COMPOSE_PATH",
    "ComposeGenerator",
    "PhpGenerator",
    "docker_generators",
]
