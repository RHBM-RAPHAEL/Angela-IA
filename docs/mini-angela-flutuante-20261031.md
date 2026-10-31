# Ângela AI — Miniatura flutuante, arrastável e sincronizada

## Finalidade

A miniatura permanece visível acima de janelas comuns como Opera GX,
sem transformar o holograma principal em uma janela que bloqueia cliques.
A miniatura só ocupa 124 x 146 pixels; o restante da tela fica livre.

## Cores dos estados reais (fonte única angela/states.py)

- Vermelho: inicializando;
- Azul: pronta/aguardando a palavra Ângela;
- Verde: ouvindo seu comando;
- Laranja: falando;
- Laranja: processando um pedido, com texto PENSANDO.

O círculo animado usa os níveis reais recebidos do microfone e do TTS.
A miniatura reutiliza o PNG do lobo salvo em
`D:\RHBM TechWorks\Meus Softwares\Angela-IA\assets\icone angela.png`
e usa `launcher/assets/AngelaAI.ico` se o PNG original for movido.

## Interação

- Arraste a miniatura com o botão esquerdo para qualquer posição,
  inclusive em outro monitor.
- A posição é salva nas configurações locais do usuário via QSettings.
- Clique com o botão direito e selecione Ocultar mini-Ângela;
  se a bandeja do Windows estiver disponível, o ícone da Ângela
  permite escolher Mostrar mini-Ângela ou dar duplo clique para restaurar.
- A miniatura nunca abre um segundo microfone, câmera ou processo de IA.
- O menu da miniatura não encerra a Ângela.
- Ao encerrar a Ângela, a miniatura e seu ícone na bandeja são fechados.

## Comportamento seguro

- Miniatura: `Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`.
- `Qt.WindowDoesNotAcceptFocus` evita roubar foco ao arrastar.
- O holograma principal mantém `Qt.WindowTransparentForInput`.
- A miniatura é registrada na lista de janelas excluídas de capturas
  internas por Windows SetWindowDisplayAffinity, se suportado.
- Sobreposição não é garantida sobre jogos em fullscreen exclusivo;
  para esses jogos, modo janela/sem bordas é mais compatível.

## Testes

Seis testes Qt específicos validam cores, estados, tamanho, janela topmost,
renderização offscreen, arraste com persistência e integração com estados.
A suíte total do Windows passou com 334 testes em 31/10/2026.
É necessário conferir a posição, visibilidade real sobre Opera e os
cinco estados com uma interação por voz no Windows.
