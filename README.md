# Jarvis PC

Asistente de voz liviano para Windows. Se le habla desde el casco ("Hey Jarvis" o una tecla) y contesta por el audio de la PC, con voz argentina.

- **Cero VRAM:** todo corre en el procesador. Los juegos tienen la placa de video entera.
- **Liviano:** esperando usa ~1-1,5 GB de RAM y casi nada de CPU. Solo trabaja un par de segundos cuando le hablan.
- **Privado:** la voz se procesa en la PC. A internet solo salen el clima y, si lo conectás, Google Calendar y Tasks.
- **Sin IA conversacional:** entiende órdenes concretas, con variaciones de cómo se dicen. Así es rápido y predecible.

## Qué se le puede pedir

| Para | Ejemplos |
|---|---|
| Timers | "poné un timer de diez minutos", "timer de 5 minutos para los fideos", "cuánto falta", "cancelá el timer" |
| Alarmas | "alarma a las siete", "despertame mañana a las 7 y media", "qué alarmas tengo", "borrá la alarma" |
| Recordatorios | "recordame mañana a las cinco llevar la carpeta" (te avisa en la PC y, con Google, también en el celular) |
| Calendario (Google) | "agregá dentista al calendario el jueves a las 4", "qué tengo hoy", "qué tengo mañana" |
| Tareas (Google Tasks) | "anotá estudiar matemática", "agregá comprar cartulina a la lista", "qué tengo anotado", "tachá estudiar matemática" |
| Música | "poné música", "pausá", "pasá el tema", "tema anterior", "qué tema es este" |
| YouTube | "buscá en YouTube cómo hacer slime" |
| Apps | "abrí ChatGPT", "abrí Discord", "abrí Minecraft" (las que estén en la lista) |
| Volumen | "subí el volumen", "bajá el volumen", "volumen al 30", "silencio" |
| Luz | "prendé la luz", "apagá la luz" (con lámpara WiZ o enchufe Shelly) |
| PC | "suspendé la PC", "apagá la PC" (las dos piden confirmación), "cancelá el apagado", "bloqueá la PC" |
| Clima | "va a llover mañana", "qué temperatura hace" |
| Otros | "qué hora es", "qué día es hoy", "modo juego", "buenas noches", "qué podés hacer" |

**"Buenas noches"** pausa la música, apaga la luz, te recuerda la alarma de mañana y pregunta si suspende la PC.
**"Modo juego"** apaga el "Hey Jarvis" (así no se activa con Discord o con el juego) y deja solo la tecla.

## Instalar

En la PC donde se va a usar, abrí **PowerShell** (no hace falta que sea como administrador) y pegá:

```powershell
irm https://raw.githubusercontent.com/martinviretti/jarvis-pc/main/instalar.ps1 | iex
```

Si el repo es privado: descargá el ZIP desde GitHub (botón Code → Download ZIP), descomprimilo y en esa carpeta corré:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

El instalador:
1. Instala `uv` y un Python 3.12 propio para Jarvis (no toca el Python que ya tenga la PC).
2. Descarga los modelos: voz argentina, detector de "Hey Jarvis" y Parakeet para entender español (~800 MB, una sola vez).
3. Crea los accesos: arranque con Windows, escritorio y menú Inicio → Jarvis.
4. La primera vez abre la **configuración**:
   - elegís el micrófono del casco y lo probás;
   - apretás la tecla para hablar (recomendado F9 o un botón lateral del mouse);
   - calibrás "Hey Jarvis" con la voz de quien lo va a usar;
   - si ya tenés lámpara, la configurás;
   - opcional: conectás Google.

Todo queda en `%LOCALAPPDATA%\JarvisPC`.

## Cómo se usa

- **"Hey Jarvis"** → suena un "tic" → decís la orden. Pronuncialo como en inglés: *jei YAR-vis*.
- **Tecla:** mantenela apretada mientras hablás y soltala. Es lo mejor mientras jugás.
- El **ícono en la bandeja** (al lado del reloj) cambia de color: celeste esperando, verde escuchando, naranja pensando, violeta en modo juego, rojo silenciado.
- Aparece una **notificación** con lo que entendió y lo que hizo. Si entendió mal, se ve enseguida.
- **Clic derecho en el ícono:** silenciar, modo juego, probar la voz, configuración, historial, conectar Google, buscar actualización, salir.

El micrófono siempre es el del casco. Jarvis contesta por la salida de audio activa en Windows: el casco o los parlantes del monitor.

## Agregar apps para abrir por voz

Clic derecho en el ícono → **Configuración**. En la sección `apps` va el nombre que se dice y qué abrir:

```yaml
apps:
  chatgpt: "https://chatgpt.com"
  discord: "discord://"
  minecraft: 'C:\Users\TU-USUARIO\Desktop\Minecraft.lnk'
  fortnite: 'C:\Users\TU-USUARIO\Desktop\Fortnite.url'
```

Para juegos de Steam o Epic: creá el acceso directo en el escritorio desde el launcher y poné su ruta. Guardá el archivo y reiniciá Jarvis (Salir y abrir de nuevo).

## Luz de la pieza

Sirve una **lámpara WiZ** o un **enchufe/relé Shelly**, porque se pueden controlar dentro de la red de la casa, sin la nube del fabricante. Las genéricas "Smart Life/Tuya" no sirven así de fácil.

1. Instalá la lámpara con la app del fabricante y conectala al Wi-Fi.
2. Buscá su IP (en la app o en el router) y, si podés, reservala en el router.
3. Menú Inicio → Jarvis → **Configurar Jarvis** → paso 4. Prueba prenderla y apagarla.

## Conectar Google (calendario y tareas)

Se hace **una sola vez**. El proyecto de Google lo creás vos con tu cuenta; tu hijo solo inicia sesión al final. Los menús de Google cambian seguido: si algún nombre no coincide, buscá el equivalente.

1. Entrá a <https://console.cloud.google.com/> y creá un proyecto llamado `Jarvis`.
2. En **APIs y servicios → Biblioteca**, habilitá **Google Calendar API** y **Google Tasks API**.
3. En **Google Auth Platform** (o "Pantalla de consentimiento de OAuth"):
   - Tipo de usuario: **Externo**. Nombre de la app: `Jarvis`. Poné tu email.
   - En **Público**: agregá la cuenta de Google de tu hijo como usuario de prueba y después tocá **Publicar app** (pasar a producción). Si queda "en prueba", Google pide volver a iniciar sesión **cada 7 días**.
4. En **Clientes** → **Crear cliente** → tipo **App de escritorio** → descargá el JSON.
5. Guardalo como `%LOCALAPPDATA%\JarvisPC\datos\google_credenciales.json`.
6. Menú Inicio → Jarvis → **Conectar Google**. Se abre el navegador: tu hijo inicia sesión y acepta. Si aparece "Google no verificó esta app", tocá *Configuración avanzada → Ir a Jarvis* (es tu propia app).
7. Reiniciá Jarvis.

Notas:
- Si la cuenta de tu hijo está supervisada con **Family Link**, quizás tengas que aprobar el acceso desde tu cuenta.
- Los **recordatorios con hora** se crean como evento del calendario con aviso, para que suenen en el celular. Google Tasks guarda la fecha pero no la hora.
- El acceso se puede revocar cuando quieras en <https://myaccount.google.com/permissions>.

## Problemas comunes

| Pasa esto | Probá esto |
|---|---|
| "Hey Jarvis" no responde | Decilo como en inglés y más cerca del micrófono. Menú Inicio → Jarvis → **Calibrar Hey Jarvis**. Siempre está la tecla |
| Se activa solo | Calibrá de nuevo o subí `sensibilidad_hey_jarvis` en la configuración (por ejemplo a 0.6). Usá "modo juego" |
| La tecla no anda dentro de un juego | Algunos juegos corren como administrador y Windows no deja que otros programas lean las teclas. Usá "Hey Jarvis" o un botón del mouse |
| No escucha nada | Revisá que el mic del casco no esté silenciado (botón del casco o Windows). Configurar Jarvis → probar el micrófono |
| "Suspendé la PC" la hiberna | Pasa si la hibernación está activada en Windows. Es normal: se despierta igual |
| La alarma no se escuchó | Suena por el audio activo de la PC. Si no tenía puesto el casco y el sonido salía por ahí, no la oyó. Para avisos importantes, usá recordatorios con Google (suenan en el celular) |
| No arranca | Mirá `%LOCALAPPDATA%\JarvisPC\datos\jarvis.log` |

**Despertar la PC suspendida por voz no se puede:** suspendida, nada escucha el micrófono. Se despierta con una tecla o el mouse.

## Actualizar y desinstalar

- **Actualizar:** clic derecho en el ícono → *Buscar actualización*, o volvé a correr la línea de instalación. La configuración, el historial y Google se conservan.
- **Desinstalar:** menú Inicio → Jarvis → *Desinstalar Jarvis*. Pregunta si conservar tus datos.

## Privacidad

- El audio se procesa en la PC y no se guarda.
- El historial (lo que se pidió y qué contestó) queda solo en `datos\historial.jsonl` y se puede apagar con `historial: false`.
- Jarvis no manda mensajes, no compra nada y no hace nada fuera de lo que figura en la tabla.

## Cómo funciona por dentro

```
casco (mic) ─▶ "Hey Jarvis" (openWakeWord) o tecla ─▶ graba hasta que hay silencio
            ─▶ Parakeet v3 (voz a texto, CPU) ─▶ reglas en rioplatense ─▶ acción
            ─▶ Piper es_AR-daniela (texto a voz, CPU) ─▶ salida de audio de Windows
```

| Pieza | Qué es |
|---|---|
| [openWakeWord](https://github.com/dscripka/openWakeWord) | Detecta "Hey Jarvis" en el procesador |
| [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) vía [onnx-asr](https://github.com/istupakov/onnx-asr) | Voz a texto multilingüe, versión int8, 2 hilos |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) con `es_AR-daniela-high` | Voz argentina |
| Google Calendar y Tasks API | Calendario y tareas |
| Open-Meteo | Clima, sin clave |

Código: `jarvis/intents.py` (qué entiende), `jarvis/nucleo.py` (qué hace), `jarvis/texto.py` (fechas y horas).
Tests: `python -m pytest`. Prueba sin micrófono: `python herramientas/prueba_sin_mic.py "poné un timer de diez minutos"`.

## Para más adelante

Con una placa de 24 GB se puede sumar un modelo de IA local para charlar y responder preguntas, sin tocar lo demás: lo que no entienda como orden se le pasa al modelo.
