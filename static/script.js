// --- Mapa base ---
const CENTRO_DEFECTO = [-17.3895, -66.1568]; // Cochabamba, Bolivia — ajusta si tu zona es otra
const map = L.map("map").setView(CENTRO_DEFECTO, 13);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

// --- Estado ---
let selectedLatLng = null;
let pendingMarker = null;
let pendingBlob = null;
let bloqueosCount = 0;

const iconoPendiente = L.divIcon({
  className: "",
  html: '<div class="marker-pending"></div>',
  iconSize: [16, 16],
});

function iconoBloqueo() {
  return L.divIcon({
    className: "",
    html: '<div class="marker-bloqueo"><div class="ping"></div><div class="dot"></div></div>',
    iconSize: [18, 18],
  });
}

// --- Elementos del DOM ---
const coordsReadout = document.getElementById("coordsReadout");
const btnAnalizar = document.getElementById("btnAnalizar");
const resultadoDiv = document.getElementById("resultado");
const listaBloqueos = document.getElementById("listaBloqueos");
const contador = document.getElementById("contador");

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const btnCamara = document.getElementById("btnCamara");
const btnCapturar = document.getElementById("btnCapturar");
const inputArchivo = document.getElementById("inputArchivo");
const previewWrap = document.getElementById("previewWrap");
const preview = document.getElementById("preview");
const btnLimpiar = document.getElementById("btnLimpiar");

let stream = null;

// --- Selección de ubicación en el mapa ---
map.on("click", (e) => {
  selectedLatLng = e.latlng;
  coordsReadout.textContent = `lat ${e.latlng.lat.toFixed(5)}, lng ${e.latlng.lng.toFixed(5)}`;

  if (pendingMarker) map.removeLayer(pendingMarker);
  pendingMarker = L.marker(e.latlng, { icon: iconoPendiente }).addTo(map);

  actualizarBotonAnalizar();
});

// --- Cámara ---
btnCamara.addEventListener("click", async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    video.srcObject = stream;
    video.classList.remove("hidden");
    btnCapturar.classList.remove("hidden");
  } catch (err) {
    alert("No se pudo acceder a la cámara: " + err.message);
  }
});

btnCapturar.addEventListener("click", () => {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);

  canvas.toBlob((blob) => {
    pendingBlob = blob;
    mostrarPreview(URL.createObjectURL(blob));
    detenerCamara();
    actualizarBotonAnalizar();
  }, "image/jpeg", 0.92);
});

function detenerCamara() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  video.classList.add("hidden");
  btnCapturar.classList.add("hidden");
}

// --- Subir foto ---
inputArchivo.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  pendingBlob = file;
  mostrarPreview(URL.createObjectURL(file));
  actualizarBotonAnalizar();
});

function mostrarPreview(url) {
  preview.src = url;
  previewWrap.classList.remove("hidden");
}

btnLimpiar.addEventListener("click", () => {
  pendingBlob = null;
  preview.src = "";
  previewWrap.classList.add("hidden");
  inputArchivo.value = "";
  actualizarBotonAnalizar();
});

function actualizarBotonAnalizar() {
  btnAnalizar.disabled = !(selectedLatLng && pendingBlob);
}

// --- Analizar con el modelo ---
btnAnalizar.addEventListener("click", async () => {
  if (!selectedLatLng || !pendingBlob) return;

  btnAnalizar.disabled = true;
  btnAnalizar.textContent = "Analizando...";
  resultadoDiv.classList.add("hidden");

  const formData = new FormData();
  formData.append("file", pendingBlob, "captura.jpg");

  try {
    const resp = await fetch("/api/predict", { method: "POST", body: formData });
    if (!resp.ok) throw new Error("Error del servidor");
    const data = await resp.json();

    mostrarResultado(data);

    if (data.es_bloqueo) {
      registrarBloqueo(selectedLatLng, data.confianza);
    } else if (pendingMarker) {
      map.removeLayer(pendingMarker);
      pendingMarker = null;
    }

  } catch (err) {
    resultadoDiv.textContent = "No se pudo conectar con el servidor: " + err.message;
    resultadoDiv.className = "resultado alerta";
    resultadoDiv.classList.remove("hidden");
  } finally {
    btnAnalizar.textContent = "Analizar imagen";
    // limpiar imagen pendiente para la siguiente captura; la ubicación se mantiene si quieres reintentar
    pendingBlob = null;
    preview.src = "";
    previewWrap.classList.add("hidden");
    inputArchivo.value = "";
    actualizarBotonAnalizar();
  }
});

function mostrarResultado(data) {
  resultadoDiv.classList.remove("hidden", "ok", "alerta");
  if (data.es_bloqueo) {
    resultadoDiv.classList.add("alerta");
    resultadoDiv.innerHTML = `⚠ <strong>Bloqueo detectado</strong><br>Confianza: ${(data.confianza * 100).toFixed(1)}%`;
  } else {
    resultadoDiv.classList.add("ok");
    resultadoDiv.innerHTML = `✓ Sin bloqueo<br>Confianza: ${(data.confianza * 100).toFixed(1)}%`;
  }
}

// --- Registro de bloqueos confirmados ---
function registrarBloqueo(latlng, confianza) {
  if (pendingMarker) {
    map.removeLayer(pendingMarker);
    pendingMarker = null;
  }

  const marker = L.marker(latlng, { icon: iconoBloqueo() }).addTo(map);
  const hora = new Date().toLocaleTimeString();
  marker.bindPopup(`<strong>Bloqueo</strong><br>${hora}<br>Confianza: ${(confianza * 100).toFixed(1)}%`);

  bloqueosCount++;
  contador.textContent = `(${bloqueosCount})`;

  const vacio = listaBloqueos.querySelector(".log-empty");
  if (vacio) vacio.remove();

  const item = document.createElement("li");
  item.className = "log-item";
  item.innerHTML = `
    <div class="coords mono">lat ${latlng.lat.toFixed(5)}, lng ${latlng.lng.toFixed(5)}</div>
    <div class="meta">${hora} · confianza ${(confianza * 100).toFixed(1)}%</div>
  `;
  item.addEventListener("click", () => {
    map.flyTo(latlng, 16);
    marker.openPopup();
  });
  listaBloqueos.prepend(item);
}