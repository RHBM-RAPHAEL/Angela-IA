# Ângela AI

Assistente pessoal gratuita e de código aberto para Windows, com reconhecimento de fala Vosk, voz feminina Dora/Kokoro e chat Groq opcional.

**Versão atual: protótipo 0.4.** Não acessa câmera, tela nem executa comandos irrestritos de computador.

## Novidade: diga "Ângela" sem clicar em Ouvir

A versão 0.4 acrescenta um controle explícito: **Ativar escuta por 'Ângela' (microfone contínuo)**.

O recurso começa **desligado**. Quando marcado:

1. Diga **"Ângela"** em voz normal, aguarde o reconhecimento.
2. Ela diz **"Oi! Estou ouvindo."**, usando a voz feminina Dora.
3. Em até **10 segundos**, diga: **"Abra a calculadora"**.
4. Também é possível falar diretamente: **"Ângela, abra a calculadora"**.
5. Para parar, desmarque a opção. Ao fechar a janela, a escuta também para.

A escuta é inteiramente local com o Vosk já instalado. Áudio do microfone não é salvo em arquivos. Durante a resposta da Dora, o reconhecimento contínuo é pausado para diminuir o risco de a assistente responder à própria voz. O botão manual **Ouvir (8 s)** continua disponível e assume o microfone de forma exclusiva.

**Importante:** a palavra-chave usa transcrição de fala em português do Vosk, e não um detector dedicado. Em ambientes barulhentos, pode não detectar seu nome, reconhecer palavras parecidas ou disparar indevidamente. Por isso a função é opcional e fica desativada após reiniciar.

## Atualizar da versão 0.3

Feche a janela aberta e execute no terminal PowerShell do VS Code:

    cd "D:\RHBM TechWorks\Meus Softwares\Angela-IA"
    git pull origin main
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    .\.venv\Scripts\python.exe -m angela

**Não é necessário** reinstalar o Ollama, as bibliotecas ou os modelos de voz: usamos as instalações que já foram testadas. Seu arquivo privado .env será mantido.

## Testes no notebook

- Marque a opção de escuta contínua e verifique a indicação **Escutando: diga 'Ângela'**.
- Diga **"Ângela"**; espere a Dora responder **"Oi! Estou ouvindo."**.
- Diga **"Abre a calculadora"** antes de o tempo de espera acabar.
- Diga **"Ângela, mude o tema do Windows para claro"**, tudo em uma frase.
- Desmarque a escuta e tente chamar de novo: a Ângela não deve reagir.
- Teste o botão manual Ouvir e o chat digitado para verificar que continuam funcionando.

Se não reconhecer seu nome, envie o texto que aparece no chat e informe se o microfone contínuo mostrou algum erro.

## Recursos

- Comandos locais: abrir calculadora, Bloco de Notas, Explorador, VS Code; mudar tema do Windows.
- Reconhecimento local por microfone com Vosk português (modelo pequeno).
- Síntese de voz feminina brasileira Dora pf_dora via Kokoro ONNX local, sem internet após a instalação.
- Chat online opcional com Groq usando openai/gpt-oss-20b (requer chave em GROQ_API_KEY no .env).
- Alternativas de voz: Windows SAPI (quando houver voz feminina pt-BR) e Microsoft Edge TTS (pode retornar 403).
- Código Python/Tkinter com MIT; modelos e dependências têm suas próprias licenças.

## Primeira instalação

Python 3.12 e Git são recomendados:

    git clone https://github.com/RHBM-RAPHAEL/Angela-IA.git
    cd Angela-IA
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m angela.download_model
    Copy-Item .env.example .env
    .\.venv\Scripts\python.exe -m pip install -r requirements-voice-kokoro.txt
    .\.venv\Scripts\python.exe -m angela.download_kokoro
    .\.venv\Scripts\python.exe -m angela

## Privacidade e segurança

- A escuta contínua começa desligada; o usuário decide quando permitir o microfone aberto.
- O reconhecimento da palavra-chave é processado localmente e não salva gravações.
- A Dora fala localmente. Apenas o texto de pedidos não locais pode ser enviado à Groq se houver chave configurada.
- O aplicativo pausa o reconhecedor durante a própria fala e durante tarefas. Isso **reduz**, mas não elimina totalmente, falsos acionamentos.
- Não executa comandos arbitrários produzidos pela IA: há uma lista restrita de ações no módulo angela/actions.py.
- Senhas, chaves de API, .env e modelos de áudio não entram no repositório público.

## Testes de desenvolvimento

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Os testes automatizados simulam a transcrição e a lógica de ativação; o funcionamento real precisa ser validado com microfone físico. A integração com Flutter, a câmera e automações mais amplas serão consideradas após estabilizar a ativação.
