# Ângela AI — Correção do botão Procurar pastas (31/10/2026)

## Problema

Os eventos Windows Application Hang 1002 de 13h34 e 13h41 registraram
AngelaAI.exe sem resposta enquanto o usuário interagia com o cadastro
de pastas; a segunda reprodução foi especificamente ao clicar Procurar.
Mesmo com salvar/remover/abrir em thread auxiliar, o antigo método
`QFileDialog.getExistingDirectory` ainda era síncrono e acionava o
seletor nativo de pastas dentro do thread Qt principal.

## Alteração

O botão Procurar agora expande um navegador de diretórios INLINE.
Não usa QFileDialog, caixa nativa Windows, exec() nem modal Qt.
Lista as unidades, subpastas e a pasta atual por operações os.scandir
em thread auxiliar. Resultados voltam à interface via sinal Qt.
Possui Voltar, Ir, Unidades, Usar esta pasta, Fechar busca.
É possível digitar/colar o caminho manualmente como antes.
Um pedido lento de disco não interrompe o processamento da interface.
A validação final da pasta no momento de Salvar continua em thread auxiliar.

## Testes

Suite Windows (QT_QPA_PLATFORM=offscreen): 349 testes, EXIT 0.
Cobertos navegar, entrar, voltar, usar pasta, salvar, abrir, remover,
resposta Qt sob atraso na validação de pasta e preservação do cadastro.
Um problema de limpeza de objetos Qt no teste foi corrigido usando
deleteLater + processamento final de eventos; também passou com EXIT 0.

## Limites

Não se abriu a janela real pelo mouse automatizado do usuário; testar
o novo Procurar visualmente na sessão Windows continua recomendado.
Discos indisponíveis podem demorar a listar mas não bloqueiam o Qt.
Não alterar arquivos nem criar pastas somente por navegação.
