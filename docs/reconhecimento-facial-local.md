# Ângela AI — Reconhecimento facial local de Rafael

O módulo angela/face_identity.py usa OpenCV YuNet e SFace somente no Windows.
O reconhecimento é local e opcional, separado das descrições enviadas à Groq.

## Comandos

- Eu sou o Rafael: entende a apresentação, oferece cadastro com consentimento.
- Cadastre meu rosto: pergunta antes de tirar foto e guardar modelo biométrico.
- Você me reconhece pela câmera?: solicita autorização para nova foto e compara.
- Ative a câmera: mantém consentimento original; se houver cadastro, pode
  mencionar correspondência local antes da descrição de imagem pela Groq.
- Apague meu cadastro facial: só exclui após nova confirmação.

Cada foto exige consentimento. Não há câmera contínua nem foto armazenada.
Uma apresentação verbal não constitui prova de identidade.

## Preparar dependências no Windows

    python -m pip install -r requirements-face.txt
    python -m angela.download_face_models

Modelos oficiais OpenCV Zoo: YuNet detector (MIT) e SFace recognizer (Apache-2.0).
https://huggingface.co/opencv/opencv_zoo/tree/main/models/face_detection_yunet
https://huggingface.co/opencv/opencv_zoo/tree/main/models/face_recognition_sface

O downloader valida tamanhos e rejeita ponteiros Git LFS. As ONNX ficam
em models/face/, ignoradas pelo Git e carregadas apenas quando necessário.

## Privacidade

- Somente o vetor numérico facial normalizado é armazenado, jamais a foto.
- Referência cifrada com DPAPI CurrentUser, acessível no perfil Windows:
  %LOCALAPPDATA%/AngelaAI/face_profile.dat.
- Comparações são locais; nenhuma referência biométrica vai para Groq.
- Descrições de câmera continuam sendo enviadas à Groq só após consentimento.
- O comando de exclusão remove o registro local após confirmação.

## Limites

O reconhecimento facial pode errar e ser enganado por fotos. Não usar para
autenticação, permissões, transações ou autorização de ações sensíveis.
O retorno indica apenas que o rosto parece corresponder ao cadastro.
Os testes automatizados usam imagens/extratores simulados; ainda faltam testes
de câmera real e de DPAPI no Windows. Nenhum rosto real foi cadastrado.
