# Ângela AI — Primeira fase de autoaperfeiçoamento controlado

## Objetivo

Permitir à Ângela melhorar o reconhecimento de nomes com correções
explícitas de voz, persistentes após reiniciar. Nenhuma LLM pode
alterar de modo arbitrário os arquivos principais ou executar código
por conta própria. Autoalteração irrestrita não é equivalente a
aprendizado de máquina e pode causar falhas graves de segurança.

## Treinamento por voz

- Diga: 'Ângela, aprenda que espotifau significa Spotify'.
- A resposta informa se a correção foi aprendida.
- Em comandos futuros, 'abra o espotifau' vira 'abra o Spotify'.
- Diga: 'Ângela, quantas correções você aprendeu?' para consultar.
- O vocabulário permitido inicial contém apenas nomes conhecidos:
  Spotify, Valorant, Discord, Roblox, Steam, YouTube, GitHub, VS Code
  e Alanzoka. Expressões comuns como 'valor' e comandos sensíveis
  não podem virar novos gatilhos de maneira silenciosa.

## Como o código é atualizado

O gerador produz uma tabela Python estritamente literal em:
`%LOCALAPPDATA%\AngelaAI\learning\learned_voice_rules.py`.
O arquivo é compilado para checar sintaxe e inspecionado via AST
com `ast.literal_eval` (nunca importado nem executado).
A correção é testada em frase controlada antes de substituir o
arquivo, usando gravação temporária e troca atômica. O gerador
não pode adicionar imports, chamadas de função, subprocessos,
instalação de pacotes, shell ou acesso ao registro do Windows.
Este arquivo de dados-código fica no perfil local, não no GitHub.

## Melhorias a partir de feedback

Os botões Sim / Não sobre execução agora atualizam estatísticas
agrupadas por tipo de falha: câmera, pastas, fala, aplicativo e outros.
Apenas o tipo e a contagem vão para:
`%LOCALAPPDATA%\AngelaAI\learning\feedback_summary.json`.
Quando há 3+ avaliações negativas do mesmo tipo, a Ângela consegue
apontar o assunto que precisa de revisão. Nenhuma correção
de código é fabricada automaticamente a partir de um Não.

## Proteções

- Não treina a partir da câmera, microfone em segundo plano ou
  conversas sem um comando explícito de correção.
- Não modifica sistemas de pagamento, segurança, reconhecimento facial
  ou inicialização do Windows automaticamente.
- Não extrai segredos nem copia conversas para serviços externos.
- Uma tabela gerada com código suspeito é rejeitada, não importada.
- Não envia commits nem publica uma alteração de código por conta própria.
- Mudanças em módulos complexos continuam exigindo revisão e testes.

## Testes

8 novos testes cobrem: comando explícito, integridade do módulo,
resistência a código executável, proibição de reescrita perigosa,
correções persistentes, integração com a engine e estatísticas.
Suíte integral no Windows: 377 testes aprovados em 31/10/2026.

## Limite do estágio

Isto é aprendizado incremental baseado em regras verificáveis.
Não é retreinamento neural de pesos nem agente de código autônomo.
Para sugerir mudanças mais amplas, etapa futura: propostas isoladas,
comparação de testes e desempenho, revisão humana e rollback.
