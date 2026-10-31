# Correção de responsividade — cadastro de pastas

## Problema reproduzido em 31/10/2026

O Windows registrou um evento Application Hang 1002 do AngelaAI.exe
às 13:34:41. A janela 'Ângela AI · Minhas pastas' exibiu
'Não está respondendo' durante tentativa de salvar:

- Apelido: Curso de programação
- Caminho: D:\Curso de Dart e Flutter\Dart\exercicios_dart

Verificou-se que o caminho existe e é uma pasta local.
O arquivo folder_aliases.json não existia após a falha; cadastro não
foi concluído pela janela. Não há evidência suficiente para atribuir
a origem única da trava a uma chamada específica do Qt.

## Proteção implementada

- Salvamento e validação de pasta, abertura do Explorer e remoção passaram
  para operações em thread auxiliar; não bloqueiam o loop gráfico Qt.
- Os resultados são enviados à thread de interface via sinal Qt.
- Os botões são desativados somente enquanto a operação está pendente,
  evitando cliques duplicados e corrupção de dados.
- A interface mostra 'Verificando pasta...' e depois o resultado ou erro.
- Testes simulam acesso lento e verificam que o Qt mantém atualização
  dos controles durante o processamento.
- Não executa comandos arbitrários, não cria pasta e não muda arquivos
  dentro do diretório do usuário.

## Cadastro solicitado

O cadastro 'Curso de programação' foi registrado diretamente em
%LOCALAPPDATA%\AngelaAI\folder_aliases.json e confirmado após nova leitura.
Agora diga: 'Ângela, abra a pasta Curso de programação'.

## Testes e ressalvas

- 349 testes automatizados passaram no Windows.
- A correção previne bloqueio da janela por operações de cadastro;
  não garante que outros componentes do Qt jamais possam travar.
- Verificar a interação real com mouse e microfone após nova execução.
