# Momentos que importaram

Rascunho da Fase 0, escrito na hora; revisar e escolher 2 a 4 antes da entrega.

1. **A IA errou o índice de coluna na checagem da Ponte.** Pedimos para confirmar `Valor ME × PTAX × Spread %` contra `Spread R$`; a IA usou a coluna da moeda no lugar do valor em ME e o script quebrou (`InvalidOperation`). Percebemos pelo erro, a IA corrigiu o índice e refez a checagem, que mostrou diferença de até R$ 0,04, coerente com a decisão do ~R$ 0,03 já tomada.
2. **O dicionário de dados estava errado, e a IA conferiu em vez de aceitar.** O dicionário diz haver, além da `PC-0926-0162`, um par com mesmo CNPJ/valor/moeda/data. Ao agrupar nas linhas reais, o único grupo era a própria repetida; registramos a correção em `HIPOTESES.md` e mantivemos a regra de "mesmos campos" só como guarda.
3. **Uma checagem ingênua da IA gerou falso positivo.** A lista de "taxas da Orbe fora da aba" incluiu 2,19 e outras taxas válidas por comparar `Decimal` como texto (`2.1900` × `2.19`). A divergência por EC/faixa, calculada na sequência, mostrou o quadro real: 4 das 5 taxas são da Atlas e 4,09 é divergência da Rota Global.
4. **A IA apontou uma ambiguidade do plano que mudaria o número.** Ao calcular a base da remessa, a IA notou que o critério A4 ("− negativos") levaria a 75.417,66 se lido como subtração de módulo, quando subtrair os valores negativos faz a base subir para 79.085,76. Registramos a leitura correta em `HIPOTESES.md` antes de implementar a remessa.
