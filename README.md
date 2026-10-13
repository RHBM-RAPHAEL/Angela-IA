# Ângela AI

Assistente pessoal gratuita e de código aberto para Windows. Comandos locais, reconhecimento de voz em português e voz feminina.

**Status:** protótipo v0.3. Ainda sem ativação contínua por "Ângela", acesso à câmera ou controle irrestrito do Windows.

## Atualizações da v0.3

- Dora local: voz feminina brasileira pf_dora via Kokoro ONNX, sem servidor de áudio externo.
- Modelo Groq corrigido para openai/gpt-oss-20b. Configurações antigas com llama-3.3-70b-versatile no arquivo .env são migradas em memória automaticamente.
- Seleção de voz: Automático (Dora -> Windows -> Francisca), Dora (local), Windows (offline) ou Francisca (online).
- Erros de áudio agora ocultam URLs temporárias e tokens do Edge TTS.
- Os testes automatizados não substituem o teste real do alto-falante no Windows.

Dora usa modelo compactado (~114 MB) e arquivos de voz (~28 MB). É executado localmente após a instalação inicial, sem Ollama ou GPU obrigatória. Dependências opcionais não são instaladas ao usar apenas o reconhecimento de fala.

## Atualizar quem já instalou a v0.2

**Feche a janela da Ângela** e execute cada linha no PowerShell do VS Code:

    cd "D:\RHBM TechWorks\Meus Softwares\Angela-IA"
    git pull origin main
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m pip install -r requirements-voice-kokoro.txt
    .\.venv\Scripts\python.exe -m angela.download_kokoro
    .\.venv\Scripts\python.exe -m angela

Na interface, selecione **Dora (local)** e clique em **Testar voz**. O primeiro carregamento pode levar alguns segundos. Depois, teste também a conversa: "O que é Python?".

Caso Dora não fale, envie a mensagem curta de erro exibida no chat. Não compartilhe sua chave Groq nem o arquivo .env.

O arquivo .env anterior é preservado pelo git pull. Você pode editar manualmente GROQ_MODEL=openai/gpt-oss-20b, mas a versão 0.3 já migra o identificador antigo automaticamente. Groq exige chave própria e tem limites no plano gratuito.

## Primeira instalação

Pré-requisitos: Git e Python 3.12 com Tkinter.

    git clone https://github.com/RHBM-RAPHAEL/Angela-IA.git
    cd Angela-IA
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m angela.download_model
    Copy-Item .env.example .env
    .\.venv\Scripts\python.exe -m pip install -r requirements-voice-kokoro.txt
    .\.venv\Scripts\python.exe -m angela.download_kokoro
    .\.venv\Scripts\python.exe -m angela

## Comandos de exemplo

- Olá, Ângela
- Abra a calculadora
- Abra o bloco de notas
- Abra o explorador de arquivos
- Abra o VS Code
- Mude o tema do Windows para claro
- Coloque o Windows no modo escuro
- O que é Python? (requer chave Groq)

O botão Ouvir recebe áudio durante até oito segundos, somente quando solicitado. O Vosk faz reconhecimento local.

## Testes

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

## Segurança e privacidade

- .env, modelos e arquivos de áudio não entram no Git.
- Voz Dora funciona localmente depois da instalação; reconhecimento Vosk também é local.
- Francisca via Edge TTS é online e pode falhar com HTTP 403, enviando o texto ao serviço.
- Groq recebe mensagens de texto para responder somente se uma chave estiver configurada.
- A IA não executa comandos arbitrários: apenas ações de sistema previstas no código.
- A voz feminina SAPI do Windows depende de haver uma voz pt-BR compatível instalada.

## Fontes e licenças

- Kokoro ONNX (MIT): https://github.com/thewh1teagle/kokoro-onnx
- Kokoro-82M (Apache 2.0): https://huggingface.co/hexgrad/Kokoro-82M
- Misaki/eSpeak: https://github.com/hexgrad/misaki
- Licença do aplicativo: MIT, ver LICENSE.

## Próximos passos

Validar voz Dora no Windows e depois implementar a ativação opcional por "Ângela", interface Flutter e ações guiadas com permissões.
