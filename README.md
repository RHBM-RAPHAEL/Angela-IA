# Ângela AI

Assistente pessoal de código aberto para Windows. Interface em português, comandos locais, reconhecimento de voz com Vosk, síntese de voz feminina e conversa opcional com Groq.

> **Status:** protótipo v0.2. O controle do Windows é limitado a ações específicas. Ainda não há câmera, controle geral do computador, interface Flutter ou ativação contínua pela palavra “Ângela”.

## O que funciona nesta versão

- Conversa por texto.
- Abre calculadora, Bloco de Notas, Explorador de Arquivos e VS Code.
- Altera o tema claro/escuro do Windows 10/11.
- Reconhece fala em português localmente pelo botão **Ouvir (8 s)**.
- Tenta reproduzir voz feminina pt-BR **Francisca** via serviço online Edge TTS.
- Se o áudio online falhar, tenta uma **voz feminina pt-BR local** instalada no Windows Speech (SAPI).
- Botão **Testar voz** e seletor do mecanismo: **Automático**, **Francisca (online)**, **Windows (offline)**. Erros de voz aparecem no chat para diagnóstico.
- Perguntas gerais pela API Groq, somente se você configurar uma chave gratuita com limites de uso.

A voz local depende de uma voz **feminina pt-BR compatível com SAPI** instalada no sistema. Nem todas as vozes que aparecem nas Configurações do Windows são acessíveis pelo SAPI. Caso não exista uma voz compatível, a opção offline mostra um erro informativo e a opção online Francisca continua disponível.

## Instalação (PowerShell do VS Code)

Pré-requisitos: Git e Python 3.12 (com Tkinter).

\`\`\`powershell
cd "D:\RHBM TechWorks\Meus Softwares"
git clone https://github.com/RHBM-RAPHAEL/Angela-IA.git
cd Angela-IA
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m angela.download_model
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m angela
\`\`\`

### Para quem já instalou a v0.1

Feche a janela antiga e, no diretório do projeto:

\`\`\`powershell
git pull origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m angela
\`\`\`

Não apague nem publique \`.env\`; contém configurações pessoais e eventualmente uma chave de API.

## Teste de voz (importante)

1. Confirme que o áudio do Windows sai pelo dispositivo correto e que o volume está audível.
2. Clique em **Testar voz**, começando por **Francisca (online)**, com internet.
3. Se não ouvir, leia a mensagem **Falha na saída de voz** exibida no próprio chat.
4. Experimente **Windows (offline)**; a voz feminina brasileira local precisa estar instalada e acessível ao Windows Speech.
5. Por fim teste **Automático (online → offline)**. Ele tenta a Francisca e recorre à voz local quando necessário.

A voz online envia **o texto da resposta**, não o áudio captado no microfone, ao serviço Microsoft Edge TTS. O reconhecimento por Vosk ocorre localmente. Ao usar Groq, o texto da pergunta é enviado à API para gerar resposta; nunca compartilhe sua chave.

## Comandos

\`\`\`text
Olá, Ângela
Abra a calculadora
Abra o bloco de notas
Abra o explorador de arquivos
Abra o VS Code
Mude o tema do Windows para claro
Coloque o Windows no tema escuro
O que é Python?   (requer chave Groq)
\`\`\`

## Testes

\`\`\`powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
\`\`\`

Os testes de fallback simulam serviços de voz, não testam alto-falantes físicos do seu computador.

## Segurança

O programa só executa ações locais explícitas de uma lista permitida. Respostas da IA não são executadas como código. \`.env\`, modelos baixados e arquivos temporários são ignorados pelo Git. O microfone só grava após o botão **Ouvir**, por até oito segundos.

## Arquitetura

\`\`\`text
angela/
  __main__.py
  ui.py             # interface Tkinter + botão Testar voz
  assistant.py      # roteamento de pedidos
  actions.py        # ações seguras Windows
  chat.py           # Groq opcional
  speech.py         # microfone Vosk + Edge TTS + Windows SAPI
  download_model.py # instalação do modelo de reconhecimento
tests/
\`\`\`

## Próximas etapas

Estabilizar saída de voz em Windows; adicionar detector da palavra "Ângela" ativável pelo usuário, interface Flutter, câmera/tela por permissão e automação guiada com confirmação para ações sensíveis.

## Licença

MIT — veja \`LICENSE\`.
