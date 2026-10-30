# Ângela AI — Assistente para Windows

Projeto pessoal de código aberto. A Ângela reconhece a palavra "Ângela" pelo Vosk local, responde com voz feminina Dora/Kokoro e pode consultar Groq opcionalmente.

**Versão 0.5 — protótipo.** Ações de Windows ampliadas, mas ainda sem visão de tela, câmera, envio de WhatsApp ou automação geral por mouse.

## O que há de novo na v0.5

- Descobre aplicativos sem cadastro manual, consultando atalhos do Menu Iniciar, App Paths do Registro e Get-StartApps da Microsoft Store.
- Abre aplicativos encontrados pelo nome: Chrome, Opera, WhatsApp ou outros registrados. Quando encontrar vários nomes próximos, pede para escolher.
- Lista e pesquisa aplicativos instalados.
- Abre pastas dos SSDs: diga "Abra a pasta Imagens no SSD D" ou informe um caminho como D:\Imagens. Valida se existe antes de abrir.
- Lista janelas visíveis e solicita fechamento normal via WM_CLOSE, mediante confirmação explícita. Não encerra processos à força.
- Diálogo para escolher entre programas e confirmar ou cancelar fechamento. As solicitações pendentes expiram após 90 segundos.
- Mantém a escuta por "Ângela", Dora local, comandos anteriores, arquivos de modelo e seu .env intactos.

## Atualizar da versão 0.4 (PowerShell do VS Code)

Feche primeiro a janela da Ângela:

    cd "D:\RHBM TechWorks\Meus Softwares\Angela-IA"
    git pull origin main
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    .\.venv\Scripts\python.exe -m angela

Não precisa reinstalar voz nem Ollama.

## O que testar

1. Marque "Ativar escuta por 'Ângela'".
2. "Ângela, quais aplicativos instalados?"
3. "Ângela, abra o Opera" — se houver Opera e Opera GX, escolha pelo número.
4. "Ângela, abra a pasta Imagens no SSD D" — deve abrir a pasta D:\Imagens.
5. "Ângela, quais janelas abertas?"
6. "Ângela, feche a calculadora" — deve pedir confirmação. Teste "cancelar" e depois "sim" caso não haja trabalho não salvo.
7. Verifique a voz Dora e os comandos anteriores.

Alguns apps portáteis sem atalhos ou registro ainda podem não aparecer. O catálogo é atualizado a cada cinco minutos, ou imediatamente quando você pede para listar os aplicativos.

## Privacidade e limitações

- Não executa comandos arbitrários de terminal. Apenas ferramentas locais implementadas e explícitas.
- Fechar uma janela exige confirmação e envia a solicitação normal do Windows; programas podem pedir para salvar o trabalho.
- Abrir pasta não significa abrir ou executar arquivos. A versão atual aceita caminhos de unidades locais, não caminhos de rede.
- Mensagens como "mande WhatsApp para minha mãe" não são executadas; o envio exigirá futura integração autorizada, seleção do contato e confirmação.
- A lista de aplicativos e janelas é consultada localmente, sem passar para a Groq.
- Voz Dora e palavra de ativação usam bibliotecas locais; microfone contínuo começa desligado e só é ativado pelo usuário.
- O reconhecimento do nome utiliza transcrição Vosk e ainda pode errar em ambientes barulhentos.
- Ainda não há acesso a todos os programas, visão de tela, automação completa de interface ou controle da câmera.

## Instalação nova

Pré-requisitos: Git, Python 3.12, Windows 10/11.

    git clone https://github.com/RHBM-RAPHAEL/Angela-IA.git
    cd Angela-IA
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m angela.download_model
    Copy-Item .env.example .env
    .\.venv\Scripts\python.exe -m pip install -r requirements-voice-kokoro.txt
    .\.venv\Scripts\python.exe -m angela.download_kokoro
    .\.venv\Scripts\python.exe -m angela

## Arquitetura da v0.5

- angela/windows_apps.py: inventário e abertura dos apps registrados.
- angela/windows_folders.py: caminhos dos SSDs e abertura de pastas.
- angela/windows_windows.py: janelas visíveis e WM_CLOSE.
- angela/windows_controller.py: comandos, escolhas e confirmações.
- angela/assistant.py: roteamento de pedidos para ferramentas locais e chat.
- angela/ui.py, wake.py, speech.py: janela, escuta por nome e voz Dora.

Executar testes:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Os testes no GitHub simulam as ações. O funcionamento com apps e janelas reais deve ser validado no seu notebook.

Licença MIT. Dependências e modelos mantêm suas respectivas licenças.


## Microfone e sensibilidade de voz (29/10/2026)

A escuta local foi atualizada com ganho automático limitado, proteção contra
saturação e escolha da entrada de áudio que realmente esteja entregando sinal.
Não altera o volume global do Windows nem grava arquivos de áudio.

- Primeiro tenta a captura compartilhada WASAPI na taxa nativa do dispositivo.
- Se a entrada devolver silêncio digital absoluto, procura a entrada física
  WDM-KS correspondente ao mesmo conjunto de microfones.
- Se o dispositivo alternativo não abrir, tenta o microfone padrão do Windows.
- WDM-KS de dois canais: seleciona o canal físico com maior sinal de voz sem misturar fases opostas.
- Converte o fluxo em memória para PCM mono de 16 kHz antes do Vosk.
- O ganho máximo padrão é 10x, com limitação de pico e supressão de ganho no
  silêncio. Pode ser ajustado sem mudar o volume global do computador.
- A espera pela palavra de ativação usa um único reconhecedor Vosk;
  apenas quando uma fala termina um segundo passe analisa alguns segundos
  de áudio mantidos em memória, para recuperar comandos ditos junto ao nome.
- A barra de microfone do painel reage à voz antes mesmo da palavra de ativação.
- Após ouvir “Ângela” isoladamente, a escuta começa imediatamente, sem aguardar uma saudação online.
- O log local inclui somente indicadores de intensidade de áudio e a fonte
  selecionada, nunca áudio bruto. Transcrições continuam seguindo as
  regras locais de histórico de conversas já existentes.

Variáveis de ambiente opcionais (definir antes de iniciar o aplicativo):

```powershell
$env:ANGELA_MIC_MAX_GAIN = "10"
$env:ANGELA_MIC_DEVICE = "default"  # Força o microfone padrão, se necessário
# Alternativa: $env:ANGELA_MIC_DEVICE = "20"   # Índice depende do computador
$env:ANGELA_MIC_PREFER_WASAPI = "0"  # Desativa seleção automática de WASAPI/WDM-KS
```

Não é preciso definir essas variáveis para usar a seleção automática. O
dispositivo WDM-KS pode ter restrições de compartilhamento; em chamadas ou
gravações simultâneas use `ANGELA_MIC_DEVICE=default`.

Teste em voz normal, sem gritar: confira a barra de microfone; diga "Ângela" e, quando a interface mostrar "Ouvindo...", diga
"abra a calculadora". Teste também "Ângela, abra o Opera" na mesma frase.
Se o microfone continuar falhando, consulte a entrada escolhida no log local
`%LOCALAPPDATA%\AngelaAI\logs\history.jsonl` através dos eventos
`microphone_open`, `microphone_probe` e `mic_signal_level`.

## Visão computacional de tela (Ângela)

A Ângela agora consegue interpretar **uma captura da tela sob demanda** e
responder por voz usando Groq Qwen 3.8 Vision. Não faz monitoramento contínuo.

Diga "Ângela", depois "o que tem na minha tela?" ou "analise a janela ativa".
A assistente pede autorização **por captura**; diga "sim" para permitir o envio
de uma imagem à Groq ou "cancelar" para não transmitir. Use "janela ativa" se
quiser restringir a imagem ao aplicativo em primeiro plano.

A aura e o painel são excluídos das capturas em Windows compatível. Não são
gravados screenshots no disco nem adicionados ao histórico ou aos logs.

**Importante:** esconda senhas e informações confidenciais antes de autorizar.
Consulte [a documentação de visão](docs/visao-de-tela.md) para mais detalhes.

## Visão pela câmera (webcam)

A Ângela reconhece pedidos como **"Ângela, você consegue me ver pela câmera?"**
e **"o que você está vendo pela webcam?"**. A câmera continua desligada
até o usuário **autorizar explicitamente cada foto e envio à Groq**.
Após a captura de um único quadro, a webcam é desligada automaticamente.

A foto fica temporariamente em RAM, não é gravada no disco nem enviada
aos logs. Não há filmagem contínua ou reconhecimento de identidade pelo rosto.
Para trocar de webcam, use `ANGELA_CAMERA_INDEX=0` (índice conforme o
Windows). O backend reutiliza o Qt Multimedia já instalado.

Leia [o guia da visão pela webcam](docs/visao-webcam.md) antes de
compartilhar imagens pessoais. A visão de tela segue funcionando separadamente.


## Janelas inteligentes sob demanda (29/10/2026)

Pedidos explícitos como "me mostre a previsão do tempo", "mostre um vídeo
de Python", "mostre fotos de pugs" ou "mostre uma explicação sobre Python"
agora passam por um roteador de resultados: ele decide entre falar, mostrar
uma janela Qt reutilizável ou usar o navegador para pesquisas/imagens.

A previsão consulta Open-Meteo em tempo real (sem utilizar GPS); a cidade
padrão pode ser definida em .env com ANGELA_WEATHER_CITY=Itirapina.
Para vídeos, a janela usa YouTube, sem reprodução automática e com opção
"Abrir no navegador" quando não houver suporte à incorporação.
A hora continua sendo respondida somente por voz. O conteúdo gerado por IA
é texto plano, sem executar códigos, e a visão de tela/câmera continua
exigindo autorização por captura.

Veja docs/janelas-dinamicas.md. A interface completa não foi iniciada
durante os testes da implementação: exige validação visual posterior.


## Executável com nome Ângela AI no Windows

O microfone deixa de ser atribuído ao Python quando a assistente é iniciada
pelo novo executável AngelaAI.exe, que hospeda o mesmo interpretador Python.
O build e o atalho de área de trabalho ficam em launcher/ (veja
launcher/README.md). Processos iniciados pelo comando antigo continuam a ser
identificados como Python. A mudança de nome depende de reiniciar pelo novo
atalho; nenhuma configuração global do Python foi modificada.
