# Revisão dos relatórios locais — 30/10/2026

## Fontes consultadas

- Registro local de conversa: %LOCALAPPDATA%/AngelaAI/conversation.jsonl.
- Feedback local: %LOCALAPPDATA%/AngelaAI/feedback.jsonl.
- Auditoria local: %LOCALAPPDATA%/AngelaAI/logs/history.jsonl.
- Não havia exportações manuais em pasta reports no momento da inspeção.
- Não foram copiados trechos privados de conversas para o repositório.

## Resultados

- 152 entradas de conversa registradas no momento da revisão.
- 20 avaliações: 17 positivas e 3 negativas.
- As 3 avaliações negativas envolviam pedidos relacionados à calculadora.
  Verificar se o programa realmente abriu antes de anunciar sucesso.
- Em conversa recente, um pedido de vídeo sobre programação Python
  foi transcrito com nome do assunto incorreto. Trata-se de provável
  erro de reconhecimento de fala, e não erro de abertura de janela.
- A previsão meteorológica foi identificada corretamente e exibiu uma
  janela com dados. Um defeito no fechamento dessa janela foi corrigido
  anteriormente no commit 1cd849e.
- A captura de câmera solicita consentimento, mas em algumas conversas
  a resposta do modelo de visão negou ou contradisse suas capacidades.
  Requer teste de regressão controlado, sem expor imagens privadas.

## Latência amostrada (dados locais históricos)

- wake_to_command: p50 ~5,32 s, 6 amostras.
- command_dispatch: p50 ~0,665 s, 6 amostras.
- tts_first_audio: p50 ~4,25 s, somente 3 amostras.
- voice_end_to_audio: p50 ~8,08 s, somente 3 amostras.
- tts_total: p50 ~17,34 s, somente 3 amostras.
- camera_capture: 3,89 s, 1 amostra.
- visual_analysis: 1,07 s, 1 amostra.

Esses valores NÃO são benchmark comparativo robusto: poucos eventos,
horários e condições diferentes, e são calculados a partir de logs.
Os rótulos voice_end_to_audio e wake_to_command dependem dos timestamps
do pipeline, não da detecção física exata do fim da fala do usuário.

## Correção do nome exibido pelo Windows

- Causa: o microfone era aberto pelo processo python.exe.
- Solução: launcher/AngelaAI hospeda CPython em AngelaAI.exe.
- Metadados FileDescription e ProductName definidos como Ângela AI.
- Build Release possui WinExe; atalho na área de trabalho criado.
- 267 testes automatizados aprovados com a nova versão presente.
- Foi iniciado o executável próprio; logs registram microphone_open.
- Ainda é necessário confirmar visualmente o texto do indicador do
  Windows em uso real no computador.

## Pendências sugeridas

1. Confirmar a abertura real da calculadora antes de dizer que foi aberta.
2. Melhorar reconhecimento de palavras em inglês, como Python.
3. Verificar respostas da IA de visão que contradizem capturas autorizadas.
4. Ampliar amostras com voz real para medir a latência p50/p95.
