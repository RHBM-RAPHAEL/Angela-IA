# Ângela AI — Visão de tela (Windows)

Implementação independente do Zynix: usa uma captura única sob demanda,
interposta entre o comando de voz e um modelo multimodal Groq.

## Como testar

1. Diga “Ângela”; ao ver “Ouvindo”, pergunte “O que tem na minha tela?”
2. A Ângela informará que enviará **um JPEG do monitor principal** à Groq.
3. Responda “sim” ou “pode” para autorizar o envio, ou “cancelar”.
4. A Ângela interpreta apenas esse quadro e responde por texto e voz.

Alternativas: “Leia o erro na tela”, “Descreva o que está no meu monitor”
e “Analise a janela ativa” (restringe a captura à janela do aplicativo).

## Política de privacidade

- Não faz vídeo, captura contínua nem streaming.
- Exige autorização explícita por captura e expira em 75 segundos.
- Não captura se não houver chave GROQ_API_KEY configurada.
- Não envia a imagem caso a confirmação seja negada ou ambígua.
- A imagem é enviada à **Groq via HTTPS** após autorização, então não
  autorize com senhas, mensagens privadas ou documentos confidenciais na tela.
- Não salva JPEG no disco, logs, histórico de conversa nem banco de dados.
  Logs trazem somente dimensões, número de bytes, escopo e status.
- A IA pode descrever ou ler a imagem, mas **não pode executar instruções
  contidas na captura**, clicar, digitar nem enviar mensagens.
- O holograma e painel solicitam exclusão de captura via Windows
  WDA_EXCLUDEFROMCAPTURE quando suportado.
- Não usa uma API key diferente nem exige criar recursos de nuvem.
- A câmera física não é acessada; somente captura de janela/monitor.

## Detalhes técnicos

`screen_vision.py`: `parse_vision_request` → confirmação via
`AssistantEngine` → `capture_screen` (Pillow/ImageGrab) →
`analyze_frame` (Groq `qwen/qwen3.8-27b`) → resposta.

Imagem JPEG em RAM, dimensão máxima 1600 pixels, limite 3 MB;
`requirements.txt` inclui Pillow.

Testes: `python -m unittest discover -s tests -q`

Validado com imagem **sintética** contra o modelo real e captura **local**
do monitor, sem enviar pixels pessoais. Para homologar a tela real, é
necessário confirmar no aplicativo com a sua própria voz.

Fonte: https://console.groq.com/docs/vision
