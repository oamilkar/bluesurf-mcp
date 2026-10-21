# Manual de instalación de bluesurf-mcp

Servidor MCP local de solo lectura para consultar tickets de BlueSurf desde Cursor.
Este manual cubre el requisito de Python, la instalación, el inicio de sesión y el
registro del servidor en Cursor.

## 1. Python es obligatorio

**bluesurf-mcp requiere Python 3.10 o superior** y `pip`.

Comprueba la versión en una terminal:

```powershell
python --version
```

La salida tiene que ser `Python 3.10` o una versión mayor (`3.11`, `3.12`, `3.13`…).

En Windows, si `python` no responde, prueba el launcher:

```powershell
py -3 --version
```

Si no hay Python, o la versión es anterior a 3.10:

1. Descarga el instalador desde [python.org/downloads](https://www.python.org/downloads/).
2. En el instalador de Windows, marca **Add python.exe to PATH**.
3. Cierra y vuelve a abrir la terminal.
4. Vuelve a ejecutar `python --version`.

## 2. Instalar el MCP

Instálalo de forma global, con el mismo Python que ya usas:

```powershell
pip install bluesurf-mcp
```

En macOS y Linux el comando es el mismo. Si `pip` no corresponde a ese Python:

```powershell
python -m pip install bluesurf-mcp
```

Comprueba que el comando responde:

```powershell
bluesurf-mcp --help
```

Tiene que mostrar el uso: sin argumentos arranca el servidor; `login` y `logout`
gestionan la sesión.

Si estás en este repositorio y quieres instalar la copia local:

```powershell
pip install -e ./bluesurf-mcp
```

## 3. Autenticarse

La contraseña se guarda en el almacén del sistema operativo
(Credential Manager en Windows, Keychain en macOS, Secret Service en Linux).
El usuario queda en un archivo local, separado de la contraseña:

| Sistema | Usuario (sin contraseña) | Contraseña |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\bluesurf-mcp\config.json` | Credential Manager, servicio `bluesurf-mcp` |
| macOS / Linux | `~/.config/bluesurf-mcp/config.json` | Llavero del sistema |

Haz el login **con el mismo usuario de Windows (o de macOS/Linux) con el que abres Cursor**. El almacén de credenciales es por usuario del sistema.

```powershell
bluesurf-mcp login
```

El comando pide:

1. **Usuario de BlueSurf** (el usuario o correo con el que entras a BlueSurf).
2. **Contraseña** (no se muestra al escribir).

Después valida las credenciales contra `https://surf.bluepeople.com`. Si el
login es correcto, verás:

```text
Credenciales guardadas en el almacén del sistema.
En mcp.json no hace falta poner usuario ni contraseña.
```

Para borrar lo guardado:

```powershell
bluesurf-mcp logout
```

Si BlueSurf rechaza el usuario o la contraseña, el comando termina con
`ERROR: login rechazado` y no guarda nada. Revisa las credenciales e inténtalo
de nuevo.

## 4. Configurar el MCP en Cursor

Cursor arranca `bluesurf-mcp` por su cuenta y habla con él por la entrada y
salida estándar. Tú no dejas el servidor corriendo en una terminal.

### 4.1 Elegir dónde guardarlo

Hay dos sitios. Usa uno.

| Alcance | Cuándo | Archivo |
| --- | --- | --- |
| Tu usuario (recomendado) | Quieres BlueSurf en cualquier proyecto | Windows: `%USERPROFILE%\.cursor\mcp.json` · macOS/Linux: `~/.cursor/mcp.json` |
| Un solo proyecto | Solo ese repositorio debe ver el servidor | `.cursor/mcp.json` en la raíz del proyecto |

`%USERPROFILE%` en Windows es la carpeta del usuario, por ejemplo
`C:\Users\TuNombre\.cursor\mcp.json`.

### 4.2 Contenido de `mcp.json`

Con la instalación global, el comando es `bluesurf-mcp`:

```json
{
  "mcpServers": {
    "bluesurf": {
      "command": "bluesurf-mcp"
    }
  }
}
```

Si el archivo ya tiene otros servidores, añade solo la entrada `"bluesurf"`
dentro de `"mcpServers"`, sin borrar las demás.

Si Cursor no encuentra el comando, usa la ruta absoluta. En PowerShell:

```powershell
(Get-Command bluesurf-mcp).Source
```

En el JSON de Windows las barras invertidas se escriben dobles, por ejemplo
`"C:\\Users\\TuNombre\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\bluesurf-mcp.exe"`.


### 4.3 Activarlo en la interfaz de Cursor

1. Abre **Cursor Settings** (`Ctrl+Shift+J` en Windows y Linux, `Cmd+Shift+J` en macOS).
2. Entra en **MCP** (en algunas versiones aparece como **Tools & MCP**).
3. Comprueba que el servidor **bluesurf** está en la lista.
4. Actívalo si el interruptor está apagado.
5. Espera a que el indicador pase a conectado. Si Cursor pide aprobación para
   el servidor, acéptala.

También puedes abrir el JSON desde esa misma pantalla con **Add new MCP server**
/ **New MCP server**, o con la paleta de comandos (`Ctrl+Shift+P`) buscando
`MCP`.

Si el servidor no aparece tras guardar el archivo, recarga la ventana:
paleta de comandos → **Developer: Reload Window**.

### 4.4 Probarlo

En un chat de Agent, pide por ejemplo:

```text
Lista mis proyectos de BlueSurf
```

El agente debe poder usar estas herramientas de solo lectura:

| Herramienta | Qué hace |
| --- | --- |
| `mis_proyectos` | Proyectos del usuario (id, smallCode, code, name) |
| `buscar_mis_tickets` | Tickets asignados en un proyecto (`smallCode`, p. ej. `PROJ`) |
| `obtener_ticket` | Detalle de un ticket (`PROJ-123`) |
| `listar_adjuntos` | Archivos de la sección Files, sin descargarlos |
| `descargar_adjuntos` | Guarda esos archivos en una carpeta local |

## 5. Problemas frecuentes

**`python` no se reconoce o la versión es menor que 3.10.**  
Instala Python 3.10+ desde python.org con **Add python.exe to PATH**, cierra la
terminal y comprueba `python --version` de nuevo.

**Cursor muestra que no encuentra `bluesurf-mcp`.**  
En una terminal, `bluesurf-mcp --help` tiene que funcionar. Si ahí responde y
en Cursor no, pon en `command` la ruta que devuelve
`(Get-Command bluesurf-mcp).Source`.

**El servidor arranca y falla con «Falta configuración de autenticación».**  
Ejecuta `bluesurf-mcp login` con el mismo usuario del sistema con el que está
abierto Cursor. El login y Cursor tienen que compartir el almacén de
credenciales de esa cuenta.

**`ERROR: login rechazado`.**  
BlueSurf no aceptó el usuario o la contraseña, o `BLUESURF_BASE_URL` apunta a
otro servidor. Corrige los datos y vuelve a ejecutar `bluesurf-mcp login`.

**Al ejecutar `bluesurf-mcp` sin argumentos la terminal se queda en blanco.**  
Eso es el servidor esperando mensajes de Cursor por la entrada estándar.
Ciérralo con `Ctrl+C`. Quien debe lanzarlo es Cursor, a través de `mcp.json`.
Para comprobar que el programa está instalado, usa `bluesurf-mcp --help`.
