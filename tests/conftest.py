"""Temporários exclusivos por execução, inclusive entre contas do Windows."""
from uuid import uuid4


def pytest_configure(config):
    # O pytest cria basetemp com acesso exclusivo ao proprietário (modo 0700).
    # Uma pasta fixa criada pelo sandbox não pode ser reutilizada pelo usuário.
    # UUID evita também colisões entre execuções simultâneas. Respeitar uma
    # escolha explícita de --basetemp feita pelo operador.
    if config.option.basetemp is None:
        config.option.basetemp = str(config.rootpath / f".pytest_tmp-{uuid4().hex}")
