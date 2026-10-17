from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config"


def test_regras_carrega_com_parametros_essenciais():
    r = yaml.safe_load((CONFIG / "regras.yaml").read_text(encoding="utf-8"))
    assert r["arredondamento"]["modo"] == "ROUND_HALF_UP"
    assert r["checkout"]["base_comissao"] == "taxa_contratada"
    assert r["remessa"]["participacao_tarvo"] == 0.5
    # CNPJ é texto: como número perderia o zero à esquerda
    assert isinstance(r["remessa"]["nf_tomador"]["cnpj"], str)


def test_lojistas_carrega():
    assert "lojistas" in yaml.safe_load((CONFIG / "lojistas.yaml").read_text(encoding="utf-8"))
