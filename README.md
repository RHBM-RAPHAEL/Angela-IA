# Ângela AI

Assistente pessoal de código aberto para Windows, com interface em português, comandos locais, reconhecimento de voz opcional e síntese de voz feminina.

> **Status:** protótipo inicial (v0.1). O controle é limitado a uma lista segura de ações. Ainda não há acesso à câmera, automação irrestrita, ativação contínua por “Ângela” ou interface Flutter.

## O que a primeira versão faz

- Conversa por texto em uma janela desktop.
- Abre Bloco de Notas, Calculadora, Explorador de Arquivos e VS Code.
- Alterna o tema claro/escuro do Windows 10/11 (configurações do usuário).
- Fala em português brasileiro com a voz feminina **pt-BR-FranciscaNeural** usando Edge TTS, quando conectado à internet.
- Recebe fala do microfone (botão **Ouvir**), com Vosk leve e local.
- Responde perguntas gerais usando a API Groq **se** você configurar uma chave; sem chave, as ações locais ainda funcionam.
- Nunca executa comandos livres de terminal gerados por IA.

## Instalação — PowerShell no VS Code (Windows)

Pré-requisitos: Git e Python 3.11 ou 3.12 (com Tkinter). A versão 3.12 está nos comandos abaixo.

```powershell
git clone https://github.com/RHBM-RAPHAEL/Angela-IA.git
cd Angela-IA
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m angela.download_model
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m angela
```

O download do Vosk ocorre uma vez (modelo pequeno em português, hospedado pelo projeto Vosk). Para conversar livremente, edite o arquivo local `.env` e coloque sua chave Groq em `GROQ_API_KEY=`. **Não publique a chave, nem envie a chave em mensagens.** Sem chave, você pode testar a interface e os comandos locais.

A voz Edge TTS usa serviço online, que pode ter indisponibilidades ou limites; nenhuma assinatura é necessária para testar a biblioteca. O plano gratuito da Groq pode ter limites de uso.

## Comandos para experimentar

- `Olá, Ângela`
- `Abra a calculadora`
- `Abre o bloco de notas`
- `Abra o explorador de arquivos`
- `Abra o VS Code`
- `Mude o tema do Windows para claro`
- `Coloque o Windows no tema escuro`
- `O que é Python?` (requer chave Groq)

O botão **Ouvir** grava somente durante a escuta solicitada (até 8 segundos). O reconhecimento ocorre localmente, sem enviar o áudio ao serviço de IA. O texto reconhecido é enviado ao Groq apenas quando necessário e quando a chave estiver configurada.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Segurança e privacidade

Acesso por **lista permitida**, com ações explícitas. Respostas do modelo de linguagem não são interpretadas como código e não dão acesso irrestrito ao sistema. Os modelos de voz são baixados para `models/`, ignorado pelo Git. `.env` e arquivos temporários não são versionados.

## Arquitetura

```text
angela/
  __main__.py       # ponto de entrada
  ui.py             # interface Tkinter
  assistant.py      # roteamento de pedidos
  actions.py        # ações seguras de Windows
  chat.py           # diálogo via Groq, opcional
  speech.py         # microfone Vosk e voz Edge TTS
  download_model.py # instalação do modelo pequeno de reconhecimento
tests/
```

## Próximos passos

Ativação “Ângela” sem botão (com privacidade configurável), interface Flutter, visão de tela/câmera autorizada, automação guiada com confirmação de operações sensíveis e uma voz offline quando estiver estável.

## Licença

MIT. Consulte `LICENSE`.
