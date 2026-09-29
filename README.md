# Vibecoding para pajeros · Audiolibro

Reproductor web del audiolibro de Ramón Molina. Abre `index.html`, elige un volumen y dale play:
el texto del capítulo aparece al lado y la palabra que suena se destaca en amarillo.
Toca cualquier palabra para saltar a ese punto del audio.

## Qué hay

- `index.html`: la página completa (texto de los dos volúmenes, portadas y reproductor).
- `audio/v1/`: capítulos 1 a 12 del volumen 1 narrados por Brian (ElevenLabs).
  Los capítulos sin MP3 se leen con la voz del dispositivo, también con destacado.
- `tiempos/`: transcripción de whisper con el tiempo de cada palabra de cada MP3.
- `guiones/`: los libros adaptados para escucharse, un capítulo por `=== título ===`.
- `herramientas/generar_audiolibro.py`: genera los MP3 (ElevenLabs o voces gratis de Microsoft).
- `herramientas/alinear_tiempos.py`: sincroniza el texto con el audio y escribe los tiempos en `index.html`.

## Agregar capítulos nuevos

```bash
# 1. Generar audio (necesita ELEVENLABS_API_KEY)
python3 herramientas/generar_audiolibro.py guiones/guion_volumen_1.txt brian
# 2. Copiar cada MP3 a audio/v1/NN.mp3 (NN = número de capítulo) y subir NARRADOS en index.html
# 3. Tiempos por palabra con whisper.cpp
ffmpeg -i audio/v1/13.mp3 -ar 16000 -ac 1 /tmp/13.wav
whisper-cli -m ggml-large-v3-turbo-q5_0.bin -l es -ml 1 -sow -ojf -of tiempos/v1/13 /tmp/13.wav
# 4. Alinear
python3 herramientas/alinear_tiempos.py
```

Para probar local usa un servidor con soporte de rangos (por ejemplo `npx serve`), así funciona adelantar el audio.
