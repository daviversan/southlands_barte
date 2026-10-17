"""Validação estrutural de pendências; decisões de negócio pertencem ao cálculo."""
from decimal import Decimal
from pathlib import PurePosixPath, PureWindowsPath

from src.core.contratos import PendenciaCalculada
from src.core.saida import Origem, SaidaError


def validar_pendencia(pendencia: PendenciaCalculada) -> None:
    for campo in ("tipo", "ref_origem", "motivo", "quem_decide"):
        valor = pendencia.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise SaidaError(f"pendência.{campo}: texto obrigatório")
    if pendencia["quem_decide"] not in ("Financeiro", "Comercial"):
        raise SaidaError("pendência.quem_decide: use Financeiro ou Comercial")
    valor = pendencia.get("valor_brl")
    if not isinstance(valor, Decimal) or not valor.is_finite():
        raise SaidaError("pendência.valor_brl: Decimal finito obrigatório")
    origens = pendencia.get("origens")
    if not isinstance(origens, list) or not origens:
        raise SaidaError("pendência.origens: ao menos uma evidência obrigatória")
    for origem in origens:
        if not isinstance(origem, Origem):
            raise SaidaError("pendência.origens: use Origem")
        if not isinstance(origem.arquivo, str):
            raise SaidaError("pendência.origens: arquivo deve ser texto")
        caminho = PurePosixPath(origem.arquivo)
        if (not origem.arquivo or not origem.arquivo.strip() or "\\" in origem.arquivo
                or caminho.is_absolute() or PureWindowsPath(origem.arquivo).drive
                or ".." in caminho.parts):
            raise SaidaError("pendência.origens: arquivo relativo à entrada obrigatório")
        if not isinstance(origem.ref, str) or not origem.ref.strip():
            raise SaidaError("pendência.origens: referência obrigatória")
        if not isinstance(origem.valor, Decimal) or not origem.valor.is_finite():
            raise SaidaError("pendência.origens: valor Decimal finito obrigatório")
    # Reutiliza exatamente a regra de soma/arredondamento do gravador.
    from src.core.saida import Saida

    Saida().emitir("pendencias", {k: pendencia[k] for k in
                  ("tipo", "ref_origem", "valor_brl", "motivo", "quem_decide")}, origens)
