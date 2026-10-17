"""Pendências: validação estrutural e explicação para o financeiro (nível Extra, E2).

As decisões de negócio (o que bloqueia, qual valor) pertencem ao cálculo. Aqui:
- `explicar_pendencias` aplica o catálogo `pendencias.tipos` de `config/regras.yaml`: `quem_decide`
  (quando o catálogo define, prevalece sobre o padrão do módulo) e `sugestao` (próximo passo).
  Uma sugestão específica já trazida pela pendência (ex.: rota de um EC) é mantida. Tipo sem
  entrada no catálogo é erro de configuração: toda pendência publicada precisa de um próximo passo.
- `validar_pendencia` confere a forma (textos, lista fechada de `quem_decide`, origens, soma).
"""
from decimal import Decimal
from pathlib import PurePosixPath, PureWindowsPath

from src.core.contratos import PendenciaCalculada
from src.core.saida import QUEM_DECIDE, Origem, SaidaError


def explicar_pendencias(pendencias: list[PendenciaCalculada], regras: dict) -> list[PendenciaCalculada]:
    catalogo = ((regras or {}).get("pendencias") or {}).get("tipos")
    if not isinstance(catalogo, dict) or not catalogo:
        raise ValueError("pendencias.tipos ausente na configuração")
    for tipo, entrada in catalogo.items():
        if not isinstance(entrada, dict) or not str(entrada.get("sugestao") or "").strip():
            raise ValueError(f"pendencias.tipos.{tipo}: sugestao obrigatória")
        if "quem_decide" in entrada and entrada["quem_decide"] not in QUEM_DECIDE:
            raise ValueError(f"pendencias.tipos.{tipo}: quem_decide deve ser um de {QUEM_DECIDE}")
    faltando = sorted({p["tipo"] for p in pendencias} - set(catalogo))
    if faltando:
        raise ValueError(f"pendencias.tipos sem explicação para {faltando}")

    explicadas: list[PendenciaCalculada] = []
    for p in pendencias:
        entrada = catalogo[p["tipo"]]
        explicadas.append({
            **p,
            "quem_decide": entrada.get("quem_decide", p["quem_decide"]),
            "sugestao": (p.get("sugestao") or entrada["sugestao"]).strip(),
        })
    return explicadas


def validar_pendencia(pendencia: PendenciaCalculada) -> None:
    for campo in ("tipo", "ref_origem", "motivo", "quem_decide"):
        valor = pendencia.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise SaidaError(f"pendência.{campo}: texto obrigatório")
    if pendencia["quem_decide"] not in QUEM_DECIDE:
        raise SaidaError(f"pendência.quem_decide: use um de {QUEM_DECIDE}")
    if "sugestao" in pendencia and (not isinstance(pendencia["sugestao"], str) or not pendencia["sugestao"].strip()):
        raise SaidaError("pendência.sugestao: quando informada, texto obrigatório")
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

    colunas = ("tipo", "ref_origem", "valor_brl", "motivo", "quem_decide") + (("sugestao",) if "sugestao" in pendencia else ())
    Saida().emitir("pendencias", {k: pendencia[k] for k in colunas}, origens)
