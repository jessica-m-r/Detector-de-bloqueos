import io
import uuid
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent

# Ruta al modelo entrenado (muévelo desde notebooks/ a models/)
MODEL_PATH = BASE_DIR / "models" / "mejor_modelo_bloqueos.pth"

# Carpeta donde se guardan las imágenes analizadas, separadas por resultado
CAPTURAS_DIR = BASE_DIR / "capturas"
(CAPTURAS_DIR / "bloqueo").mkdir(parents=True, exist_ok=True)
(CAPTURAS_DIR / "no_bloqueo").mkdir(parents=True, exist_ok=True)

# Mismo orden que detectó ImageFolder (alfabético): bloqueo=0, no_bloqueo=1
CLASSES = ["bloqueo", "no_bloqueo"]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def cargar_modelo() -> nn.Module:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo en {MODEL_PATH}. "
            f"Copia 'mejor_modelo_bloqueos.pth' a la carpeta 'models/'."
        )
    modelo = models.resnet18(weights=None)
    modelo.fc = nn.Linear(modelo.fc.in_features, len(CLASSES))
    state_dict = torch.load(MODEL_PATH, map_location=device)
    modelo.load_state_dict(state_dict)
    modelo.to(device)
    modelo.eval()
    return modelo


model = cargar_modelo()

transform = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)

app = FastAPI(title="Detección de Bloqueos")


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "templates" / "index.html")


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.post("/api/predict")
async def predecir(file: UploadFile = File(...)):
    contenido = await file.read()
    try:
        img = Image.open(io.BytesIO(contenido)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer la imagen enviada")

    img_t = transform(img).unsqueeze(0).to(device)

    with torch.no_grad():
        out = model(img_t)
        probs = torch.softmax(out, dim=1)[0]
        idx = int(probs.argmax().item())
        confianza = float(probs[idx].item())

    etiqueta = CLASSES[idx]

    # Guardar la imagen analizada en capturas/<etiqueta>/
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
    ruta_guardado = CAPTURAS_DIR / etiqueta / nombre_archivo
    img.save(ruta_guardado, "JPEG", quality=90)

    return {
        "label": etiqueta,
        "es_bloqueo": etiqueta == "bloqueo",
        "confianza": round(confianza, 4),
        "archivo": str(ruta_guardado.relative_to(BASE_DIR)),
    }