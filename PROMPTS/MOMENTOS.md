# Momentos que importaram

1. **Arredondamento incorreto:** pedimos a conferência da remessa, e a IA calculou 50% do spread agregado, chegando a R$ 39.542,88. Aplicamos nossa regra de arredondamento por operação, corrigimos para R$ 39.543,45 e registramos a decisão H1 em `HIPOTESES.md` (sessões `18e4b96b` e `300d01e3`).

2. **Perguntas ao financeiro:** pedimos as perguntas ainda abertas sem fornecer as respostas anteriores, e a IA solicitou o texto em vez de inventar. Colamos as respostas, limitamos a lista a cinco perguntas sobre regras gerais e enviamos ao #tarvo-financeiro (sessão `61646267`).

3. **Duplicidade inexistente:** na preparação dos dados, a IA escreveu no dicionário que havia um segundo par de operações duplicadas na Ponte, mas a conferência das linhas reais encontrou somente a repetida já conhecida. Registramos a correção em `HIPOTESES.md` e mantivemos a checagem por campos apenas como proteção futura (sessões `c41731a8` e `18e4b96b`).

4. **Escolha do papel da IA:** pedimos que a IA explicasse o uso de um LLM para classificar os lançamentos bancários e verificamos que os 184 já eram classificados por regras. Decidimos retirar o LLM da solução, mantendo a IA na construção e na conferência, sem chave de API na execução (sessão `b0dd5359`).
