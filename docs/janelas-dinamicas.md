# Ângela AI — Janelas de resultados sob demanda

O roteador de resultados decide entre **falar**, **abrir no navegador** ou
**criar uma janela Qt**. Ele não executa HTML nem código recebido da IA.

## Exemplos

| Pedido por voz | Comportamento |
| --- | --- |
| "Ângela, que horas são?" ou "me mostre a hora" | Fala a hora local, sem janela |
| "Ângela, me mostre a previsão do tempo" | Cria janela meteorológica se cidade padrão estiver configurada |
| "Mostre a previsão do tempo em Itirapina" | Dados atuais e 3 dias via Open-Meteo |
| "Me mostre um vídeo de Python no YouTube" | Janela com pesquisa no YouTube e botão para navegador |
| "Mostre o vídeo https://youtu.be/XXXXXXXXXXX" | Incorpora vídeo do YouTube, sem autoplay |
| "Mostre a diferença entre Python e Java" | Janela de texto e resposta por voz |
| "Mostre os resultados da busca sobre energia solar" | Pesquisa no navegador existente |
| "Abra o VS Code" | Mantém abertura de aplicativos existente |
| "Mostre meus projetos" | Mantém painel de projetos existente |

O reconhecimento é conservador: a janela só surge quando o usuário pede
explicitamente mostrar, exibir, apresentar ou quero ver. Perguntas normais
continuam sendo respondidas por voz.

## Arquitetura

- angela/result_routing.py: planeja voz, clima, vídeo, navegador ou texto.
- angela/weather_result.py: dados HTTPS do Open-Meteo, com timeout e validação.
- angela/result_window.py: janela Qt para texto e vídeo, sem interpretar HTML da IA.
- angela/assistant.py: gera dados da janela fora da thread gráfica.
- angela/voice_coordinator.py: envia payload pela fila para o Qt.
- angela/desktop_overlay.py: exibe e fecha até três janelas simultâneas.

As janelas não são persistidas, e vídeos só aceitam URLs YouTube autorizadas.
O conteúdo pode não permitir reprodução incorporada por política do YouTube;
nesse caso, a janela tem botão "Abrir no navegador". Respostas da IA em
texto são exibidas como texto plano, sem JavaScript.

## Cidade padrão

A Ângela não usa GPS nem IP para localizar o notebook. Para responder a um
pedido sem mencionar a cidade, configure em .env:

    ANGELA_WEATHER_CITY=Itirapina

Também aceita "previsão do tempo em <cidade>". Sem configuração de cidade,
pede a localização desejada. A fonte meteorológica é Open-Meteo.

## Segurança e testes

- Não grava vídeo, dados de websites nem imagens da webcam.
- Não executa scripts sugeridos pelo modelo de IA.
- Mantém os comandos Windows, wake-word, microfone e captura de webcam.
- Testes usam respostas simuladas, sem conexão externa nem iniciar a Ângela.
- Não há confirmação de funcionamento visual com o áudio real até o usuário testar.

Testes: python -m unittest discover -s tests -q
