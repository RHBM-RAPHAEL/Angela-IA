# Ângela AI — Diálogo contextual e autorizações concisas

## Problemas reproduzidos no relatório de 31/10/2026

- Ao pedir uma foto de um caderno, a Ângela leu 3x + 9x = x.
- Depois de 'resolva essa equação', esqueceu a descrição anterior.
- Repetia explicações extensas sobre Groq, webcam e confirmação toda vez.
- Não ativava novamente a escuta se a interrogação não fosse o último sinal.

## Comportamento implementado

- Captura visual em nuvem: 'Posso ativar a câmera e enviar uma foto à IA para análise?'
- Reconhecimento facial local: 'Posso ativar a câmera para reconhecer seu rosto?'
- Tela: autorização curta, identificando a captura e o envio à IA.
- 'sim' autoriza somente a captura pendente; 'não' cancela.
- 'assim' ou transcrição ambígua exige repetir, nunca é autorização.
- Uma descrição textual recente da última foto autorizada fica somente em RAM,
  durante até cinco minutos, sem criar um novo arquivo de memória visual.
- Referências 'essa equação', 'qual era a equação' e 'o que você viu?'
  usam a descrição textual recente, sem tirar uma foto adicional.
- Equações lineares simples com x são resolvidas localmente com Fraction.
- Quando não há imagem recente: 'Onde está a equação? Na câmera, na tela ou pode ditá-la?'
- 'na câmera' e 'câmera' como respostas levam à solicitação de consentimento.
- Perguntas são detectadas se houver ? em qualquer trecho da resposta,
  mesmo que uma afirmação apareça depois. Estados de consentimento e
  esclarecimento também reativam a escuta sem depender de pontuação.
- O modo verde passa a ouvir assim que a fala da Ângela termina, evitando
  reconhecer a própria voz; limite de seguimento aumentado para 20 segundos.
- O contexto textual é apagado quando a sessão de voz é encerrada.

## Privacidade e limitações

- A imagem continua enviada à API de visão Groq somente após consentimento.
- A frase de autorização é curta, mas declara que a foto será enviada à IA.
- O reconhecimento facial local é separado de análises remotas.
- Não há câmera contínua, captura de tela não autorizada ou gravação de áudio.
- O histórico normal da Ângela já registra respostas textuais; esta memória
  de contexto não cria nenhum registro adicional nem salva pixels.
- Memória contextual limitada a uma captura recente, não uma memória geral.
- O solucionador local aceita apenas equações lineares simples, sem eval/exec.
- É necessário validar a experiência com voz real após reiniciar a aplicação.

## Testes

- Casos sintéticos de equação, leitura de foto, consentimento, cancelamento,
  mudança de assunto e perguntas seguidas de afirmações.
- Suíte automatizada Windows: 306 testes aprovados em 31/10/2026.
