"""
Genera el audiolibro de "Vibecoding para pajeros" con voces de hombre pro.

Dos motores:
  - edge:       voces neuronales de Microsoft. Gratis, sin cuenta, acento nativo
                (chileno, mexicano, argentino...). Corre de inmediato.
  - elevenlabs: la calidad más alta del mercado. Necesita ELEVENLABS_API_KEY.

Uso:
  pip install requests edge-tts        (y ffmpeg para unir trozos: brew install ffmpeg)

  python generar_audiolibro.py --voces                      # lista las voces incluidas
  python generar_audiolibro.py --muestras                   # 1 MP3 corto por voz para comparar
  python generar_audiolibro.py guion_volumen_1.txt          # voz por defecto
  python generar_audiolibro.py guion_volumen_1.txt lorenzo  # voz por nombre
  python generar_audiolibro.py guion_volumen_1.txt TU_VOICE_ID   # cualquier voz de ElevenLabs

Si hay ELEVENLABS_API_KEY la voz por defecto es "brian"; si no, "lorenzo" (gratis).
Crea una carpeta con un MP3 por capítulo. Si se corta, vuelve a correrlo:
se salta los capítulos que ya existen.
"""
import asyncio, os, re, subprocess, sys, tempfile, time

# ---------------------------------------------------------------- voces
# Microsoft Neural (gratis). Todas masculinas y con acento nativo.
VOCES_EDGE = {
    "lorenzo":   ("es-CL-LorenzoNeural",   "Chileno. El que calza con el libro."),
    "jorge":     ("es-MX-JorgeNeural",     "Mexicano neutro, voz grave de locutor."),
    "tomas":     ("es-AR-TomasNeural",     "Argentino, cercano."),
    "gonzalo":   ("es-CO-GonzaloNeural",   "Colombiano, muy claro."),
    "alonso":    ("es-US-AlonsoNeural",    "Latino neutro (EE.UU.), estilo doblaje."),
    "alvaro":    ("es-ES-AlvaroNeural",    "España, narrador clásico."),
}

# ElevenLabs (premium). Voces masculinas prediseñadas: IDs fijos, funcionan en
# cualquier cuenta y hablan español con el modelo multilingüe.
VOCES_ELEVEN = {
    "brian":   ("nPczCjzI2devNBz1zQrb", "Grave y resonante. Narrador de audiolibro."),
    "adam":    ("pNInz6obpgDQGcFmaJgB", "Profundo, el clásico de narración."),
    "bill":    ("pqHfZKP75CvOlQylNhV4", "Maduro y confiable, estilo documental."),
    "george":  ("JBFqnCBsd6RMkjVDRZzb", "Cálido, cuentacuentos."),
    "chris":   ("iP95p4xoKVk53GoZ742B", "Relajado y casual, buena onda."),
    "eric":    ("cjVigY5qzO86Huf0OWal", "Suave, conversacional."),
}

MUESTRA = ("Siempre quise escribir un libro, pero me daba paja. Así que hice lo que haría "
           "cualquier pajero con recursos: lo desarrollé con I A. Y eso ya es la primera "
           "lección del libro.")

# ---------------------------------------------------------------- ajustes
MODELO_ELEVEN = "eleven_multilingual_v2"
AJUSTES_ELEVEN = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.2, "use_speaker_boost": True}
EDGE_VELOCIDAD = "-4%"    # un pelo más lento que lo normal: mejor para escuchar
EDGE_TONO = "-2Hz"        # un poco más grave
MAX_CHARS = 2500          # trozos cortos = entonación más estable


def capitulos(texto):
    partes = re.split(r"^=== (.+?) ===\s*$", texto, flags=re.M)
    for i in range(1, len(partes), 2):
        yield partes[i].strip(), partes[i + 1].strip()


def trozos(texto):
    actual = ""
    for p in [p.strip() for p in texto.split("\n\n") if p.strip()]:
        if actual and len(actual) + len(p) + 2 > MAX_CHARS:
            yield actual
            actual = p
        else:
            actual = f"{actual}\n\n{p}" if actual else p
    if actual:
        yield actual


# ---------------------------------------------------------------- motores
def hablar_eleven(texto, anterior, voz, clave):
    import requests
    for intento in range(4):
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voz}",
            headers={"xi-api-key": clave, "Content-Type": "application/json"},
            params={"output_format": "mp3_44100_128"},
            json={"text": texto, "model_id": MODELO_ELEVEN, "voice_settings": AJUSTES_ELEVEN,
                  "previous_text": anterior[-1000:] if anterior else None},
            timeout=180,
        )
        if r.status_code == 200:
            return r.content
        print(f"   Error {r.status_code}: {r.text[:200]}")
        if r.status_code in (401, 402, 403):
            sys.exit("Revisa tu clave o los caracteres disponibles en tu plan.")
        time.sleep(5 * (intento + 1))
    sys.exit("No se pudo generar este trozo. Intenta de nuevo más tarde.")


def hablar_edge(texto, voz):
    try:
        import edge_tts
    except ImportError:
        sys.exit("Falta edge-tts: pip install edge-tts")

    async def _run():
        audio = b""
        com = edge_tts.Communicate(texto, voz, rate=EDGE_VELOCIDAD, pitch=EDGE_TONO)
        async for parte in com.stream():
            if parte["type"] == "audio":
                audio += parte["data"]
        return audio

    for intento in range(4):
        try:
            audio = asyncio.run(_run())
            if audio:
                return audio
        except Exception as e:
            print(f"   Error: {e}")
        time.sleep(3 * (intento + 1))
    sys.exit("No se pudo generar este trozo. Revisa tu conexión e intenta de nuevo.")


def unir_mp3(partes, ruta):
    """Une los trozos limpio con ffmpeg (sin clics); si no hay ffmpeg, los concatena."""
    if len(partes) == 1 or not _hay_ffmpeg():
        with open(ruta, "wb") as f:
            f.write(b"".join(partes))
        return
    with tempfile.TemporaryDirectory() as tmp:
        lista = os.path.join(tmp, "lista.txt")
        with open(lista, "w") as l:
            for i, p in enumerate(partes):
                trozo = os.path.join(tmp, f"{i:03d}.mp3")
                with open(trozo, "wb") as f:
                    f.write(p)
                l.write(f"file '{trozo}'\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", lista, "-c:a", "libmp3lame", "-b:a", "128k", ruta], check=True)


def _hay_ffmpeg():
    return subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0


# ---------------------------------------------------------------- elegir voz
def resolver_voz(nombre, clave):
    """Devuelve (motor, id). Acepta nombre de la lista o un Voice ID de ElevenLabs."""
    if nombre is None:
        nombre = "brian" if clave else "lorenzo"
    n = nombre.lower()
    if n in VOCES_EDGE:
        return "edge", VOCES_EDGE[n][0]
    if n in VOCES_ELEVEN or re.fullmatch(r"[A-Za-z0-9]{20}", nombre):
        if not clave:
            sys.exit(f"'{nombre}' es de ElevenLabs y falta ELEVENLABS_API_KEY. "
                     f"Usa una gratis, por ejemplo: lorenzo")
        return "elevenlabs", VOCES_ELEVEN[n][0] if n in VOCES_ELEVEN else nombre
    if re.fullmatch(r"[a-z]{2}-[A-Z]{2}-\w+Neural", nombre):
        return "edge", nombre
    sys.exit(f"Voz desconocida: {nombre}. Mira las opciones con --voces")


def listar_voces(clave):
    print("GRATIS (Microsoft Neural, sin cuenta):")
    for k, (_, d) in VOCES_EDGE.items():
        print(f"  {k:<10} {d}")
    print(f"\nPREMIUM (ElevenLabs{'' if clave else ', necesita ELEVENLABS_API_KEY'}):")
    for k, (_, d) in VOCES_ELEVEN.items():
        print(f"  {k:<10} {d}")


def generar_muestras(clave):
    os.makedirs("muestras_voces", exist_ok=True)
    voces = list(VOCES_EDGE) + (list(VOCES_ELEVEN) if clave else [])
    for nombre in voces:
        motor, voz = resolver_voz(nombre, clave)
        ruta = os.path.join("muestras_voces", f"{nombre}.mp3")
        print(f"Muestra: {nombre} ({motor})")
        audio = hablar_eleven(MUESTRA, "", voz, clave) if motor == "elevenlabs" else hablar_edge(MUESTRA, voz)
        with open(ruta, "wb") as f:
            f.write(audio)
    print("Listo. Escúchalas en la carpeta 'muestras_voces' y elige.")


# ---------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    clave = os.environ.get("ELEVENLABS_API_KEY")
    if args[:1] == ["--voces"]:
        return listar_voces(clave)
    if args[:1] == ["--muestras"]:
        return generar_muestras(clave)
    if len(args) not in (1, 2):
        sys.exit(__doc__)

    archivo = args[0]
    motor, voz = resolver_voz(args[1] if len(args) == 2 else None, clave)
    texto = open(archivo, encoding="utf-8").read()
    salida = os.path.splitext(os.path.basename(archivo))[0].replace("guion_", "audio_")
    os.makedirs(salida, exist_ok=True)
    print(f"Motor: {motor} | Voz: {voz} | Caracteres: {len(texto):,}")

    for n, (titulo, cuerpo) in enumerate(capitulos(texto), 1):
        nombre = re.sub(r"[^\w\- ]", "", titulo)[:60].strip()
        ruta = os.path.join(salida, f"{n:02d} - {nombre}.mp3")
        if os.path.exists(ruta):
            print(f"Listo antes: {ruta}"); continue
        print(f"Generando {n:02d}: {titulo}")
        partes, anterior = [], ""
        for t in trozos(cuerpo):
            if motor == "elevenlabs":
                partes.append(hablar_eleven(t, anterior, voz, clave))
            else:
                partes.append(hablar_edge(t, voz))
            anterior = t
        unir_mp3(partes, ruta)
    print(f"Terminado. Tus MP3 están en la carpeta '{salida}'.")


if __name__ == "__main__":
    main()
