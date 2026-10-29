# Ângela AI — Visão computacional pela webcam

A Ângela agora pode analisar **uma foto da webcam sob demanda**, mantendo a
visão de tela independente. Não há monitoramento contínuo ou reconhecimento
biométrico de pessoas.

## Como usar

1. Abra a Ângela e diga **"Ângela"**.
2. Pergunte: **"Você consegue me ver pela câmera?"** ou **"O que você
   está vendo pela webcam?"**. Outros exemplos: "Como estou vestido pela
   câmera?", "O que estou segurando na câmera?".
3. A Ângela explica que vai **ligar a webcam, tirar uma foto, desligá-la
   imediatamente e enviar o JPEG à Groq**. Ela exige confirmação para esse
   envio; responda **"sim"** ou **"cancelar"**.
4. A câmera é iniciada somente após essa autorização, captura um único
   quadro e é desligada independentemente de sucesso ou erro.
5. A resposta da IA aparece no painel e pode ser lida por voz.

O painel exibe **"Câmera ligada · capturando uma única foto"** enquanto a
captura estiver em andamento e **"Câmera desligada"** ao terminar.

**Importante:** não autorize a câmera se estiver mostrando algo pessoal
que não deseja enviar à Groq. Não serão salvas fotos localmente, mas a foto
confirmada será processada pelo serviço externo. A câmera não é uma
transmissão contínua.

## Arquitetura

- `angela/camera_vision.py`: reconhecimento conservador de intenção e
  captura com limite de 14 segundos em um processo filho isolado.
- `angela/camera_worker.py`: cria o Qt na sua própria thread principal,
  utiliza `QMediaDevices.videoInputs()`, `QCamera`, `QMediaCaptureSession`
  e `QVideoSink` e devolve um único JPEG por pipe em memória.
- O Qt Multimedia da webcam não é mais inicializado na thread de voz da
  Ângela: isso evita o travamento da interface identificado após a foto.
- Se o processo filho falhar ou exceder o limite, será encerrado e a
  Ângela poderá informar a falha em vez de ficar congelada.
- Sem OpenCV nem serviços adicionais; reutiliza o Qt instalado no Windows.
- Uma solicitação `VisionRequest(scope="camera")` cria confirmação
  independente de tela e com validade de 75 segundos.
- Para cada nova foto, é necessária nova autorização.
- A câmera padrão é **a primeira entrada informada pelo Windows**.
  Para escolher outra, defina `ANGELA_CAMERA_INDEX` com o índice numérico
  antes de executar a Ângela (por exemplo, `0` para webcam principal).
- Conversão e compactação em RAM para JPEG de até 1280 px e 3 MB.
- `analyze_frame` utiliza o modelo visual já configurado na Groq
  (`qwen/qwen3.8-27b`) com prompt específico para fotos da webcam.
- Não é possível pedir à IA que **identifique a pessoa pelo rosto**, nem
  afirmar a identidade ou inferir atributos sensíveis de alguém.
- Textos que apareçam na foto não podem comandar a IA ou o computador.

## Privacidade, limitações e testes

- Captura somente uma foto após autorização explícita.
- A câmera fica **desligada por padrão** e é liberada no bloco `finally`.
- Não produz vídeo, streaming, reconhecimento facial persistente ou
  gravação oculta.
- O aplicativo não salva fotos, não envia as imagens para logs e não mantém
  as imagens no histórico de conversas.
- O recurso pode falhar se a webcam estiver indisponível, bloqueada pelas
  permissões do Windows ou ocupada por outro aplicativo.
- A câmera integrada Acer foi detectada; também há uma câmera virtual
  cadastrada pelo Windows. A captura real só deverá ocorrer mediante
  autorização expressa dada diretamente à Ângela.
- Testes automáticos usam imagens **sintéticas** e mocks da câmera.
- Não habilite o acesso à webcam antes de verificar se a câmera
  pretendida está apontada para você.

Para testar:

```powershell
cd "D:\RHBM TechWorks\Meus Softwares\Angela-IA-HUD-v06"
& "C:\Users\rhbmr\AppData\Local\Programs\Python\Python312\python.exe" -m unittest discover -s tests -q
$env:ANGELA_ENABLE_VOICE="1"
& "C:\Users\rhbmr\AppData\Local\Programs\Python\Python312\python.exe" -m angela.desktop_overlay
```

Documentação técnica:
- [Qt Multimedia QVideoSink](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QVideoSink.html)
- [Qt QMediaCaptureSession](https://doc.qt.io/qtforpython-6/PySide6/QtMultimedia/QMediaCaptureSession.html)
