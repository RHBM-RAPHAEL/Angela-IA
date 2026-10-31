# Ângela AI — Memória explícita e atalhos de pastas por voz

## Memória pessoal — só quando solicitada

- 'Ângela, salve na memória que meu cachorro chama Thor'.
- 'Ângela, salve na memória' -> 'O que você quer que eu salve?'.
- No turno seguinte, a pessoa dita o fato. Um 'não' cancela.
- 'Ângela, o que você lembra de mim?' lista os fatos registrados.
- 'Qual o nome do meu cachorro?' recupera informações relevantes.
- 'Apague da memória sobre cachorro' remove entradas relacionadas.
- 'Apague da memória' pede um assunto, sem excluir tudo por engano.

Somente declarações explícitas são persistidas: a Ângela não extrai fatos
de conversas, câmera ou microfone sem o comando de salvar. Entrada limitada
a 260 caracteres; evita registrar senhas, tokens e documentos sensíveis.
Até 36 informações são guardadas em arquivo cifrado com DPAPI CurrentUser:
`%LOCALAPPDATA%\AngelaAI\personal_memory.dat`.

A recuperação pessoal acontece localmente. Memórias cifradas NÃO são
automaticamente enviadas à API Groq. A busca usa palavras relacionadas
do pedido atual, não interpreta os fatos como comandos para executar.
Importante: os registros de conversas habituais da Ângela podem conter
a frase falada original; a implementação de memória não cria logs
adicionais com os fatos completos.

## Cadastro de caminhos de pastas

- Diga 'Ângela, cadastre pastas' ou 'abra gerenciador de pastas'.
- Ou clique em Pastas na janela de conversas, ou use a bandeja do Windows.
- Na telinha, digite um apelido, por exemplo 'Meus Projetos'.
- Cole o caminho no campo: `D:\RHBM TechWorks\Meus Softwares`.
- Clique em 'Salvar pasta', ou selecione uma pasta usando 'Procurar...'.
- Depois diga 'Ângela, abra a pasta Meus Projetos'.
- É possível abrir ou remover a pasta selecionada na mesma janela.

Cadastro salvo em `%LOCALAPPDATA%\AngelaAI\folder_aliases.json`.
Só são aceitos caminhos locais absolutos existentes no Windows, sem
executar arquivos nem interpretar URLs ou comandos recebidos por voz.
A abertura usa Explorer.exe com shell=False. O apelido não dá acesso
adicional: a conta Windows precisa ter permissão na pasta.

## Limitações e privacidade

- É uma memória factual local limitada, não treinamento de um novo modelo.
- Perguntas complexas ainda podem requerer conversa externa, mas os dados
salvos não são anexados automaticamente a ela.
- Nomes ditados pelo Vosk podem ser transcritos incorretamente; a tela de
pastas ajuda a cadastrar nomes/caminhos sem ditar caracteres complexos.
- Os caminhos ficam em texto no perfil local para poderem ser editados.
- Não foram importadas automaticamente conversas privadas nem pastas.

## Testes

- Persistência simulada e DPAPI real no Windows com informações fictícias;
- Rejeição de segredos comuns, exclusão seletiva, restauração após reinício;
- Qt: colar caminho, salvar, listar, abrir e remover sem Explorer real;
- Rejeição de URLs, UNC, arquivos executáveis e caminhos inexistentes.
