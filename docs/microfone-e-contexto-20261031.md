# Correção — a Ângela dizia incorretamente que não ouvia

## Evidência de 31/10/2026

Às 10h33 o microfone abriu com source=wdmks-raw (48000 Hz, 2 canais).
O Vosk reconheceu 'você está ouvindo a minha voz'. A pergunta foi
enviada à Groq, que respondeu 'não tenho acesso ao áudio; só texto'.
Isso descreve a API remota isolada, não o programa Ângela: a captura
de microfone e a transcrição locais funcionaram.

Às 10h34 o Vosk reconheceu 'você me conhece na câmera'. A Ângela
solicitou corretamente autorização para comparação facial; no retorno
transcreveu uma possível confirmação como 'assim' e perdeu o consentimento
pendente. Uma autorização ambígua NÃO pode acionar a câmera.

RMS de entrada 22 a 40 em várias amostras depois da fala e ganho AGC
próximo de 10 vezes. Valores são eventos pontuais, não uma medição
calibrada de volume nem uma gravação.

## Correções implementadas

- A resposta sobre escuta real é agora local e factual: a Ângela usa
  o microfone e transforma áudio em texto para a interpretação.
- O prompt remoto explica que Groq recebe transcrição e não o áudio bruto.
- Em confirmação visual ou biométrica ambígua, mantém a pergunta pendente
  dentro do prazo, repete a solicitação e NÃO faz captura.
- 'não' cancela, 'sim' pode autorizar, outro assunto descarta o pedido.
- Não se grava áudio, não se abre câmera nem se envia conteúdo nos testes.

## Limitações

A execução instalada precisa ser reiniciada para carregar módulos atualizados.
O reconhecimento de voz pode continuar confundindo palavras; isso requer
comparação de ASR com frases autorizadas e eventualmente microfone mais
próximo à boca. Não alegar que a Groq recebe áudio bruto.
