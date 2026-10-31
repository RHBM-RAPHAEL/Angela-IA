# Ângela AI — Modo de visão computacional ao vivo

## Ativação pelo comando de voz

- Diga: 'Ângela, ative a visão computacional'.
- Abre uma pequena janela independente, no canto superior direito,
  com prévia local da webcam em tempo real.
- No título da janela: 'Visão computacional · ao vivo'.
- Botão 'Fechar câmera' encerra a visualização.
- Diga 'Ângela, feche a câmera' para encerrar por voz.
- Ao fechar, a câmera é interrompida e o Qt libera a sessão de captura.
- O botão Fechar não encerra a IA nem desativa o microfone.

## Contexto dos comandos

Enquanto a janela estiver aberta, pedidos como 'o que você está vendo?',
'leia essa equação', 'veja isso aqui' e 'o que estou segurando na câmera'
são interpretados como referência à câmera aberta, mesmo sem repetir
a expressão 'pela câmera'. Perguntas sobre programação, horários ou
configuração do Windows não acionam captura automaticamente.

## Privacidade e autorização

- O comando de ativar a visão computacional abre SOMENTE a prévia local.
- Não grava vídeo, som ou fotografia, não transmite stream para a internet.
- Para a IA analisar um quadro da webcam na Groq, a Ângela pergunta
  brevemente: 'Posso enviar uma foto da câmera à IA para análise?'.
- Somente após o SIM explícito o quadro atual é convertido em uma foto
  temporária em memória e enviado ao serviço de análise já configurado.
- Um NÃO cancela a operação. Consentimentos são por solicitação; ativar
  a prévia não dá autorização permanente para compartilhar imagens.
- Reconhecimento facial local possui fluxo separado de consentimento.
- Ao fechar a prévia pelo comando, autorizações pendentes são canceladas.

## Arquitetura

- camera_mode.py contém parser sem efeitos colaterais para abrir/fechar.
- camera_preview.py usa QCamera + QMediaCaptureSession + QVideoWidget
  criados e manipulados exclusivamente na thread Qt da interface.
- CameraPreviewBridge encaminha solicitações da engine por sinais Qt
  enfileirados com limite de tempo; nunca cria uma segunda QCamera para
  obter quadros durante a prévia.
- CameraPreviewWindow é uma janela Tool independente do holograma.
- Fechar via botão ou X limpa estado e interrompe a sessão.
- HologramOverlay.closeEvent também fecha a webcam antes de sair.

## Limitações

- O vídeo é exibido LOCALMENTE. Não existe análise automática quadro a quadro.
- Uma pergunta que necessite compreender pixels usa a foto autorizada
  e a API remota, não vídeo contínuo nem reconhecimento de ações em tempo real.
- Os testes automatizados simulam a câmera e o transporte de quadros;
  nenhum teste deve ativar a webcam física sem pedido específico do usuário.
- É necessário homologar a imagem real, a posição da janela e a interação
  por voz no Windows após o usuário ativar o modo.

## Testes

- Ativar e fechar por voz, botão/X simulado, prévia sem captura remota.
- Contextualizar perguntas sem menção de câmera e rejeitar assuntos externos.
- Confirmar e negar envio da foto sem iniciar câmera duplicada.
- Cross-thread Qt com janela simulada, sem acesso a webcam real.
- Suíte total executada no Windows em 31/10/2026: 315 testes aprovados.
