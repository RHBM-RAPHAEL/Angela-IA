# Ângela AI — Auditoria de falhas, 31/10/2026, 12h01

## Evidências do relatório exportado

- 'Abra o canal do YouTube do Alanzoka no Opera GX' foi reconhecido
  aproximadamente como 'abra o canal ... do alunos oca no ópera justiça'.
- A assistente perdeu a intenção do YouTube depois de pedir o nome.
- Respostas seguintes 'aula' e 'alunos oca' foram levadas à IA genérica,
  chegando à interpretação incorreta de Oracle Certified Associate.
- Perguntas 'o que é esse desenho?' e 'olhe na câmara' negaram
  incorretamente acesso à câmera, embora a prévia local estivesse ativa.
- A visão remota introduziu um aviso sobre não ativar câmera mesmo depois
  da captura autorizada, antes de descrever o desenho de um veículo.
- OCR/visão relatou uma equação confusa '3x + 9 = √10 = x'; o parser
  pegou a parte '10 = x' e resolveu erradamente x = 10.
- Comandos de fechar a webcam, abrir a prévia e analisar imagens
  com autorização funcionaram no mesmo relatório.

## Correções

1. `youtube_channels.py`: interpreta variantes observadas somente dentro
   do contexto de canal do YouTube; URL oficial de Alanzoka é fixa e
   validada: https://www.youtube.com/@alanzoka.
2. Preserva o navegador preferido e a pergunta de esclarecimento até
   a resposta seguinte ('aula', 'alunos oca', 'sim'), evitando trocar
   de assunto para curso, Java ou OCA.
3. O canal conhecido só é aberto com ação explícita; nomes ou
   destinos desconhecidos não são adivinhados e não viram URL arbitrária.
4. `camera_mode.py` reconhece perguntas sobre desenhos e objetos visíveis
   quando a prévia já está aberta. Exige autorização para foto enviada à IA.
5. `camera_vision.py` reconhece a variante 'câmara' e dá ao modelo remoto
   uma pergunta de descrição sobre a imagem já capturada, não um comando
   para abrir webcam. Remove somente o prefácio falso e conhecido.
6. `dialog_context.py` recusa trechos de equações incompletas com dois ou
   mais sinais '=' em contexto, em vez de fabricar solução para '10 = x'.

## Limitações e validação

- Correção contextual do ASR não é aumento geral de precisão do Vosk.
- O canal oficial foi verificado externamente; abertura real do navegador
  não foi realizada nos testes, apenas simulação de chamada segura.
- A webcam real não foi acionada; regressões testam intenções e consentimento.
- 328 testes automatizados aprovados no Windows após as correções.
- É necessário testar nova sessão de voz para avaliar reconhecimento real.
