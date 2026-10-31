# Ângela AI — Nomes em inglês durante comandos em português

## Motivação

A Ângela usa Vosk `vosk-model-small-pt-0.3` offline (Português do Brasil).
É comum o ASR devolver aproximações fonéticas de palavras estrangeiras
em frases como 'Ângela, abra o Spotify' e 'inicie o Valorant'.
Foi solicitado reconhecer nomes em inglês e português no mesmo comando.

## Correções implementadas

- `mixed_language_asr.py`: vocabulário inicial de nomes conhecidos:
  Spotify, Valorant, VS Code, YouTube, GitHub, Discord, Roblox, Steam.
- Corrige variantes como spotifai / espotifai / esporte fai => Spotify;
  valorante / valor rante => Valorant em conversas e comandos.
- Nomes só são normalizados quando há padrão fonético específico;
  palavras ambíguas sozinhas ('esporte', 'valor') permanecem sem alteração.
- `asr_selection.py`: em hipótese Vosk de confiança próxima (diferença
  até 0,10), pode escolher a alternativa com nome de aplicativo explícito
  SOMENTE se o pedido de ação e a transcrição primária combinarem.
  Não altera abrir para fechar nem substitui aplicativos diferentes.
- `wake.py`: aplica a normalização no texto final ouvido antes da
  entrega à interface e ao motor de comandos. Não altera a wake word.
- `speech_corrections.py`: aplica a mesma normalização a textos digitados
  e mensagens que contornam a escuta do microfone.
- Nenhum áudio é salvo, transmitido pela Internet ou enviado à LLM.
  A lista de apps instalados do Windows continua sendo a autoridade
  para executar um comando de aplicativo.
- A ambiguidade 'abra o esporte' ainda pede confirmação de Spotify
  antes de abrir. Não executa jogos por conjectura.

## Validações

- Spotify e VALORANT encontrados no catálogo de apps do Windows RHBM;
  a instalação do Valorant consta em D: e Spotify na lista StartApps.
- Testes sintéticos cobrem as variações dos dois nomes, as alternativas
  acústicas de Vosk, perguntas sem ação e comandos não relacionados.
- Suite de regressão do Windows: 366 testes aprovados em 31/10/2026.

## Limitação importante

Esta melhoria é uma normalização contextual de termos ingleses dentro
da escuta pt-BR; NÃO substitui por um modelo ASR multilíngue nem
garante entender frases inteiras em inglês. Para bilinguismo amplo
será necessário avaliar modelo local multilíngue e sua latência na
máquina Windows, preservando privacidade e robustez do wake word.
Os testes foram simulados; o usuário deve testar os nomes falando.
