# Ângela AI — Auditoria de latência (29/10/2026)

## Escopo e integridade das versões

Trabalho realizado no Linux `rhbm-dev-linux`, em um clone isolado
`Angela-IA-performance-20261029` na branch `perf/latency-audit-20261029`.
O ponto de partida é `760d8c3`, último commit existente na branch
`dev/angela-reliability-20261029` do GitHub no momento da auditoria.

**Atenção:** a instalação Windows contém commits locais posteriores
(`d3e3901`, `93e6275`), com correção da câmera e janelas inteligentes,
que não estavam na branch remota usada para este trabalho. É obrigatório
reaplicar estas otimizações SOBRE a versão Windows antes do teste final;
nunca substituir o diretório Windows por este clone antigo.

O Windows não respondeu ao Remote Desktop Commander nesta sessão.
Não foi possível coletar utilização real de CPU, RAM, RTX 3050, VRAM e
resultados de TTS diretamente do Windows nesta rodada. A Ângela não foi iniciada.

## Evidências históricas da execução Windows (anteriores a esta auditoria)

Os logs examinados no atendimento anterior, referentes ao teste autorizado
de webcam em 29/10/2026, registraram:
- Resposta sobre a webcam até o pedido de permissão: 124 ms.
- Síntese/reprodução da pergunta de consentimento pelo Edge TTS: **30.062 ms**.
  Essa duração era **total** (incluindo reprodução), não tempo até a primeira fala.
- Após o "sim", captura + análise e resposta: **5.099 ms**, incluindo
  4,1 s até a captura e cerca de 1,0 s até finalizar a análise.
- O Qt Multimedia da webcam foi isolado em processo filho por uma correção
  no commit Windows `d3e3901`, ainda ausente do ponto de partida Linux.
Esses valores são **uma observação histórica**, não média representativa
nem resultado comparativo desta auditoria.

## Problemas comprovados pelo código

1. `speech._speak_edge` exigia MP3 completo antes de chamar
   `pygame.mixer.music.play()`. Em respostas longas, era impossível iniciar
   a primeira fala enquanto a rede ainda enviava o áudio.
2. `streaming_tts.synthesize_segments` já existia, mas sua callback de
   reprodução bloqueava a próxima síntese. O caminho principal nem o usava.
3. A interface de áudio, ASR e decisões tinha alguns timestamps, mas faltavam
   métricas p50/p95 por etapa com formato uniforme e desligamento simples.
4. O log de tentativa de fala salvava o texto sintetizado; foi alterado
   para registrar apenas a contagem de caracteres nessa etapa.

## Melhorias implementadas

- `angela/streaming_tts.py`: produção em segundo plano e fila limitada
  a 2 segmentos para baixar tempo da primeira fala e sintetizar o próximo
  durante a reprodução. Frases de até aproximadamente 100 caracteres.
- `angela/speech.py`: streaming Thalita como caminho padrão, com opção
  `ANGELA_TTS_STREAMING=0` para voltar à síntese anterior, sem trocar voz;
  callback ao primeiro comando de reprodução de áudio.
- `angela/voice_coordinator.py`: mede ativação→comando, comando
  reconhecido→início do primeiro áudio e duração total de processamento
  e fala, usando relógio monotônico e trace por interação.
- `angela/perf_metrics.py`: telemetria **local opcional** desligada por
  padrão (`ANGELA_PERF_DIAGNOSTICS=1`); registra somente nome permitido
  de etapa, duração ms e status, sem conteúdo de voz ou imagens.
- `angela/perf_report.py`: relatório textual offline de p50, p95,
  média, amostras e erros, lendo apenas eventos de desempenho.
- `angela/chat.py`, `angela/agent_planner.py`, `angela/wake.py`,
  `angela/assistant.py`, `angela/camera_vision.py` e
  `angela/screen_vision.py`: métricas de API, detecção de dispositivo,
  ação local e visão sob demanda.
- Não foi alterado o modelo Vosk, limiar de ganho, wake word,
  controlador Windows, câmeras ou política de consentimento.
- No modo streaming, o nível de animação é uma oscilação visual leve;
  a extração exata do envelope MP3 foi evitada para não atrasar o áudio.

## Comparação controlada — simulação, não serviço real

Arquivo reprodutível: `benchmarks/tts_synthetic.py`.
12 repetições, mesmo texto e mesma voz configurada. Um provedor de
**rede simulado** demora 300 ms para o MP3 completo; cada um dos três
segmentos tem 100 ms. O mixer também é um mock.
As medições usam `time.perf_counter()` até a chamada `music.play()`.

| Estratégia | Média | p50 | p95 |
| --- | ---: | ---: | ---: |
| MP3 inteiro | 301,32 ms | 301,29 ms | 301,45 ms |
| MP3 segmentado | 101,07 ms | 100,98 ms | 101,16 ms |

A queda de **66,5%** é **somente do cenário sintético** para tempo até
o primeiro comando de reprodução. Não deve ser apresentada como
aceleração real da Ângela. TTS real depende da rede Edge, velocidade
do serviço, decodificador, reprodução, drivers e hardware Windows.

## Testes, hardware e limitações

- Linux: Intel Core i3-1005G1, 4 CPUs lógicas, ~19 GiB RAM.
- Nenhuma RTX/NVIDIA identificada nesta máquina Linux, e
  `nvidia-smi` não disponível. **Não houve benchmark CUDA.**
- Testes automatizados no Linux: 238 executados, 3 pulados por dependência
  de plataforma; demais aprovados. Sem abertura de GUI, microfone ou câmera.
- Faltam comparações reais (p50/p95) dos comandos Windows, rede Groq e
  Edge TTS, e medidas de RAM/VRAM e vazamentos no notebook principal.
- Plugins Datadog, PostHog, Amplitude e Datadog Experiments não foram
  usados como fonte de métricas da Ângela: não existe integração comprovada
  com a telemetria deste projeto. Nenhum dado foi publicado externamente.
- A RTX 3050 pode acelerar inferência local compatível e gráficos, mas
  não reduz latência de serviços de voz/IA executados remotamente por si só.
- O esquema de medições distingue tempo de ASR final→áudio audível;
  **não representa precisamente o instante em que o usuário parou de falar**
  sem calibração do endpoint de silêncio.

## Como testar posteriormente no Windows

Após conciliar os commits desta branch com a versão Windows mais recente:
1. Execute a suíte Windows e verifique regressões de câmera/visão/janelas.
2. Compare 20 interações por cenário, com ângela e wake reais autorizados.
3. Teste com `ANGELA_PERF_DIAGNOSTICS=1` e consulte
   `python -m angela.perf_report`. Não publique o arquivo de logs.
4. Calcule p50/p95 de `tts_first_audio`, `voice_end_to_audio`,
   `ai_total` e `command_dispatch` em condições semelhantes.
5. Se houver travamentos, defina `ANGELA_TTS_STREAMING=0` e repita o
   teste — rollback imediato sem eliminar a voz natural.
6. Quando disponível, colete também GPU/RAM/VRAM e sincronize a medição com
   um teste de TTS real, pois a GPU tem maior efeito sobre modelos locais.

**Não existe medição suficiente para concluir que a execução real no Windows
ficou 66,5% mais rápida.**
