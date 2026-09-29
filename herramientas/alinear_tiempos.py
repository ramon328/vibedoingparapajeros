"""
Sincroniza el texto del libro con los MP3 para el destacado amarillo.

1. Transcribe cada MP3 con whisper.cpp y tiempos por palabra:
     ffmpeg -i audio/v1/04.mp3 -ar 16000 -ac 1 /tmp/04.wav
     whisper-cli -m ggml-large-v3-turbo-q5_0.bin -l es -ml 1 -sow -ojf -of tiempos/v1/04 /tmp/04.wav
2. Corre este script desde la raíz del repo:
     python3 herramientas/alinear_tiempos.py
   Lee el texto de index.html (const DATA), alinea cada palabra del libro con
   lo que whisper escuchó y escribe `const TIMES = ...;` dentro de index.html.
"""
import difflib, glob, json, os, re, unicodedata

HTML = "index.html"


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", w)


def palabras_whisper(ruta):
    out = []
    for s in json.load(open(ruta, encoding="utf-8"))["transcription"]:
        for w in s["text"].split():
            if norm(w):
                out.append((norm(w), s["offsets"]["from"] / 1000))
    return out


def alinear(texto_palabras, oidas):
    libro = [norm(w) for w in texto_palabras]
    t = [None] * len(libro)
    sm = difflib.SequenceMatcher(None, libro, [w for w, _ in oidas], autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            t[a + k] = oidas[b + k][1]
    # palabras sin match: interpola entre vecinos conocidos
    conocidos = [i for i, x in enumerate(t) if x is not None]
    if not conocidos:
        return None
    fin = oidas[-1][1] + 0.5
    for i in range(len(t)):
        if t[i] is not None:
            continue
        antes = max((k for k in conocidos if k < i), default=None)
        despues = min((k for k in conocidos if k > i), default=None)
        t0 = t[antes] if antes is not None else 0.0
        t1 = t[despues] if despues is not None else fin
        i0 = antes if antes is not None else -1
        i1 = despues if despues is not None else len(t)
        t[i] = t0 + (t1 - t0) * (i - i0) / (i1 - i0)
    for i in range(1, len(t)):  # nunca hacia atrás
        t[i] = max(t[i], t[i - 1])
    return [round(x, 2) for x in t], len(conocidos) / len(libro)


def main():
    html = open(HTML, encoding="utf-8").read()
    data = json.loads(re.search(r"^const DATA = (.*);$", html, re.M).group(1))
    times = {}
    for vol in data:
        times[vol] = []
        for i, cap in enumerate(data[vol]):
            ruta = f"tiempos/{vol}/{i + 1:02d}.json"
            if not os.path.exists(ruta):
                times[vol].append(None)
                continue
            palabras = [w for p in cap["p"] for w in p.split()]
            r = alinear(palabras, palabras_whisper(ruta))
            times[vol].append(r[0] if r else None)
            print(f"{vol} {i + 1:02d} {cap['t'][:45]:<45} match {r[1]:.0%}" if r else f"{vol} {i + 1:02d} sin datos")
    linea = "const TIMES = " + json.dumps(times, separators=(",", ":")) + ";"
    if re.search(r"^const TIMES = .*;$", html, re.M):
        html = re.sub(r"^const TIMES = .*;$", lambda _: linea, html, flags=re.M)
    else:
        html = re.sub(r"^(const DATA = .*;)$", lambda m: m.group(1) + "\n" + linea, html, flags=re.M)
    open(HTML, "w", encoding="utf-8").write(html)
    print("index.html actualizado.")


if __name__ == "__main__":
    main()
