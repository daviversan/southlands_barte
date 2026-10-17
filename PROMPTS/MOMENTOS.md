# Momentos que importaram

1. **A IA errou o arredondamento da remessa, e a regra do contrato pegou o erro.** Na Fase 0 pedimos para conferir as regras de remessa contra o relatório da Ponte. A IA calculou a comissão como 50% da soma do spread, R$ 39.542,88. Ao escrever o spec do Alvo, a regra que nós demos (arredondar por linha para o rastro fechar ao centavo) mostrou que o número certo é R$ 39.543,45; registramos a decisão (H1 em `HIPOTESES.md`) antes de implementar. (Sessões `18e4b96b` e `300d01e3`.)

2. **A IA parou em vez de inventar.** Pedimos as perguntas que o financeiro ainda não tinha respondido, mas esquecemos de colar as respostas. A IA não chutou: disse que as respostas não estavam na mensagem e pediu o texto. Colamos as respostas e, depois de dois ajustes nossos (5 perguntas, regras gerais em vez de casos de lojistas), as perguntas foram para o #tarvo-financeiro. (Sessão `61646267`.)

3. **O dicionário que a própria IA escreveu estava errado, e um recálculo pegou.** O `DICIONARIO_DADOS.md` dizia haver na Ponte, além da operação repetida `PC-0926-0162`, um segundo par com mesmo CNPJ, valor, moeda e data. Na Fase 0, ao agrupar as linhas reais, o único grupo era a própria repetida. Corrigimos em `HIPOTESES.md` e mantivemos a regra de "mesmos campos" só como proteção para outubro. (Sessões `c41731a8` e `18e4b96b`.)

4. **Cortamos a IA de dentro da solução.** O plano previa um LLM para classificar lançamentos bancários que nenhuma regra pegasse. Pedimos para a IA explicar o papel do LLM, vimos que os 184 lançamentos já fecham por regra e mandamos tirar o LLM do plano. A solução roda sem chave de API; a IA ficou na construção e na conferência, não no cálculo. (Sessão `b0dd5359`.)

## Outros erros da IA que corrigimos

- Ao conferir os cartões do front, a IA leu as colunas erradas do extrato Aurora; ao conferir as notas, usou a coluna errada de vigência da planilha. Nos dois casos ela percebeu a inconsistência, refez a conta e só então confirmou os números. (Sessão `4d13c32d`.)
- Scripts de conferência com `Counter(dict)`, que conta os valores do dicionário em vez das chaves. A IA identificou como erro próprio e corrigiu. (Sessões `b0dd5359` e `4d13c32d`.)
- O README não dizia para criar o ambiente virtual, e `python -m src.main` falhou sem o `yaml`. Corrigido depois que colamos o erro. (Sessão `b0dd5359`.)
