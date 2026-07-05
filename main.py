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
MODEL_BLOQUEOS_PATH = BASE_DIR / "models" / "mejor_modelo_bloqueos.pth"
MODEL_PORTERO_PATH = BASE_DIR / "models" / "modelo_detector_calle.pth"
CAPTURAS_DIR = BASE_DIR / "capturas"
(CAPTURAS_DIR / "bloqueo").mkdir(parents=True, exist_ok=True)
(CAPTURAS_DIR / "no_bloqueo").mkdir(parents=True, exist_ok=True)
(CAPTURAS_DIR / "no_calle").mkdir(parents=True, exist_ok=True)

CLASSES_BLOQUEOS = ["bloqueo", "no_bloqueo"]
CLASSES_PORTERO = ["calle", "otros"]

UMBRAL_PORTERO = 0.6

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _cargar_resnet18(path: Path, num_classes: int) -> nn.Module:
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo en {path}. Copia el archivo .pth a la carpeta 'models/'."
        )
    modelo = models.resnet18(weights=None)
    modelo.fc = nn.Linear(modelo.fc.in_features, num_classes)
    state_dict = torch.load(path, map_location=device)
    modelo.load_state_dict(state_dict)
    modelo.to(device)
    modelo.eval()
    return modelo


def cargar_modelo_bloqueos() -> nn.Module:
    return _cargar_resnet18(MODEL_BLOQUEOS_PATH, len(CLASSES_BLOQUEOS))


def cargar_modelo_portero() -> nn.Module:
    return _cargar_resnet18(MODEL_PORTERO_PATH, len(CLASSES_PORTERO))


model_bloqueos = cargar_modelo_bloqueos()
model_portero = cargar_modelo_portero()

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


def _predecir(modelo: nn.Module, clases: list[str], img_t: torch.Tensor):
    with torch.no_grad():
        out = modelo(img_t)
        probs = torch.softmax(out, dim=1)[0]
        idx = int(probs.argmax().item())
        confianza = float(probs[idx].item())
    return clases[idx], confianza


@app.post("/api/predict")
async def predecir(file: UploadFile = File(...)):
    contenido = await file.read()
    try:
        img = Image.open(io.BytesIO(contenido)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer la imagen enviada")

    img_t = transform(img).unsqueeze(0).to(device)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"{timestamp}_{uuid.uuid4().hex[:8]}.jpg"

    etiqueta_portero, confianza_portero = _predecir(model_portero, CLASSES_PORTERO, img_t)

    if etiqueta_portero == "otros" and confianza_portero >= UMBRAL_PORTERO:
        ruta_guardado = CAPTURAS_DIR / "no_calle" / nombre_archivo
        img.save(ruta_guardado, "JPEG", quality=90)

        return {
            "es_calle": False,
            "label": "otros",
            "es_bloqueo": False,
            "confianza": round(confianza_portero, 4),
            "confianza_portero": round(confianza_portero, 4),
            "archivo": str(ruta_guardado.relative_to(BASE_DIR)),
        }

    etiqueta_bloqueo, confianza_bloqueo = _predecir(model_bloqueos, CLASSES_BLOQUEOS, img_t)

    ruta_guardado = CAPTURAS_DIR / etiqueta_bloqueo / nombre_archivo
    img.save(ruta_guardado, "JPEG", quality=90)

    return {
        "es_calle": True,
        "label": etiqueta_bloqueo,
        "es_bloqueo": etiqueta_bloqueo == "bloqueo",
        "confianza": round(confianza_bloqueo, 4),
        "confianza_portero": round(confianza_portero, 4),
        "archivo": str(ruta_guardado.relative_to(BASE_DIR)),
    }