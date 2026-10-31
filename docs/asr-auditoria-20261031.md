# Auditoria de reconhecimento de voz — 31/10/2026

## Evidência

Relatório registrado: angela_diagnostico_20261031_101822_043260.txt.
O usuário disse 'você me reconhece pela câmera' e a transcrição local foi
'você me conhece pela câmera'. Também houve cortes como 'você me'.
O interpretador facial antes não aceitava 'conhece pela câmera' e enviava
o pedido à IA de conversa, que respondeu incorretamente não ter webcam.

Os registros de mic_signal_level em uma sessão anterior mostram amostras
de fala com RMS de entrada de 18, 55 e 102, e ganhos adaptativos próximos
de 8 a 10 vezes. Essas são amostras, não uma gravação nem uma avaliação
estatística de toda a fala. Indicariam pouco sinal na entrada em momentos
específicos. Nenhum áudio privado foi gravado nesta auditoria.

## Correções implementadas

- angela/face_identity.py: aceita somente variações muito específicas de
  'você me conhece pela câmera' como pedido de comparação facial.
- angela/asr_selection.py: Vosk pode propor até três hipóteses; quando
  a principal diz 'conhece pela câmera', uma alternativa 'reconhece'
  muito próxima em confiança pode ser usada. Demais comandos preservados.
- angela/wake.py: hipóteses adicionais só na decodificação de comandos.
- angela/audio_frontend.py: ANGELA_MIC_DEVICE agora aceita índice ou parte
  do nome do dispositivo, facilitando selecionar um novo headset USB.
- Sem gravação de voz ou envio de transcrições para nova API.

## Microfone opcional

Para usar um headset USB chamado Logitech H390, por exemplo, configure
em .env ANGELA_MIC_DEVICE=H390, se esse nome aparecer nos dispositivos
de entrada. Para utilizar o padrão do Windows, use ANGELA_MIC_DEVICE=default
ou remova a variável. Troque o dispositivo somente com o aplicativo parado
e reinicie para aplicar. Nomes não encontrados geram erro explícito em vez
de selecionar outro microfone silenciosamente.

## Limitações

O Vosk local usa o modelo pequeno vosk-model-small-pt-0.3.
O modelo grande do Vosk pode exigir grande RAM e é GPLv3; não foi
instalado automaticamente. Whisper/faster-whisper pode oferecer outro
caminho, mas só deve substituir o backend após comparação com gravações
de teste autorizadas e medições de CPU/GPU, p50/p95 e precisão.

Testes automatizados demonstram correção de intenção e seleção simulada
de alternativas, mas NÃO comprovam taxa de erro de palavras menor na voz
real de Rafael. A versão que já está rodando precisa ser reiniciada em
momento autorizado para carregar o novo código.
