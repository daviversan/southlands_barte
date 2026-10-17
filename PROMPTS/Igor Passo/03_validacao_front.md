# B — suporte, validação e correções operacionais do front

**Fonte:** conversa disponível com Codex para suporte/explicações; Git e diff para
as correções posteriores de interface. Sumário complementar, sem diálogos inventados.

## Pedidos observados e verificação

| Pedido | Resposta/ação da IA | Resultado e correção |
|---|---|---|
| Explicar A/B e o que validar na inicialização | Leu código/documentos e propôs conferir conservação, taxas, pendências e rastro | 57 testes de normalização, saída e pendências passaram; suíte completa então bloqueada por dependências |
| Adaptar `.venv/bin/python` para Windows | Comando com `venv\Scripts\python.exe` | Compatível com o ambiente real informado pelo usuário |
| Executar após `ModuleNotFoundError: No module named 'yaml'` | Reproduziu erro, identificou Python 3.15 e instalou PyYAML/openpyxl | Instalação padrão tentou compilar extensão C e falhou; instalação com `PYYAML_FORCE_LIBYAML=0` dispensou o compilador |
| Explicar as linhas do rastro e sua cobertura | Mostrou ligação por id_saida, origem e contribuição monetária | Distinguiu comissão, bruto bloqueado e pendência cadastral zero; alertou que a soma geral não é receita |
| Comparar Alvo e Extra | Leu implementação atualizada e rodou testes | 176 testes passaram naquela revisão; distinguiu rastro existente de relatório/interface futuros |

## Execução bem-sucedida do Mínimo naquela sessão

```powershell
.\venv\Scripts\python.exe -m src.main --entrada context/tarvo_data_pack --competencia 2026-09 --saida saida/minimo
```

Resultado: 1.957 linhas; 1.841 vendas = 1.574 processadas + 267 bloqueadas;
38 antecipações, 69 estornos e 9 reversões fora do escopo daquela versão.
Seis CSVs gerados e **120 testes passaram**. Esses totais de processamento são
históricos do Mínimo, não os do Alvo/Extra atual.

## Onde a IA precisou corrigir a abordagem

A instalação padrão escolhida pela IA não bastou para Python 3.15: o PyYAML
tentou compilar uma extensão e exigiu ferramentas C++. O usuário trouxe o erro
real de execução; a IA reproduziu, instalou a variante Python puro e executou
novamente. Os relatos anteriores de dependências pendentes não viraram alegações
retroativas de testes bem-sucedidos.

## Front e permissões: reconstrução por evidências

- Front/Extra iniciais: registros originais de A em `../Davi Versan/04_extra_front.md`.
- `e2bd3ae`: correção das permissões dos CSVs publicados e tratamento de erros no front.
- `e36c4c2`: integração do front com essas correções.
- A publicação passou a tratar permissões herdadas da pasta pai: mover arquivos
  de temporário privado podia impedir leitura por outra conta no Windows.
- No início desta consolidação havia alterações locais de upload: lote exclusivo,
  preservação de nomes/bytes, validação dos documentos e explicação da análise afetada
  por arquivo ausente. O lote enviado é usado sozinho; sem envio, vale o exemplo.

Não há prompts originais dessas correções posteriores nesta conversa; o Git e o
diff comprovam mudanças de código, não a sequência exata de pedidos. Outros trabalhos
em paralelo alteraram o estado local durante esta documentação, inclusive com conflito
em `src/app.py`. Esta sessão não resolveu nem sobrescreveu essas alterações.

## Limites

Teste com Streamlit simulado não atesta apresentação visual. Não se atribuiu a B a
validação no navegador relatada por A. Testes automáticos também não substituem
gabarito da banca ou revisão humana cruzada.
