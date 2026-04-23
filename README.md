# Explorador NPN

Complemento para [QGIS](https://qgis.org) que, sobre la capa vectorial elegida, lee en tiempo real el atributo de un campo (Número Predial Nacional, NPN), lo valida y desglosa el **No Predial** de 30 dígitos según la estructura de referencia (departamento, municipio, zona, sector, comuna, etc.).

## Requisitos

- QGIS superior a **3.0** a **3.99**. Se recomienda la rama 3.3x LTR o la más reciente compatible.
- Capas **vectoriales** (punto, línea o polígono) con el campo a consultar.

## Instalación

1. Copia la carpeta `npn_explorer` al directorio de complementos de Python de tu perfil de QGIS, por ejemplo:
   - **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\<perfil>\python\plugins\`
2. En QGIS: **Complementos → Gestionar e instalar complementos → Instalado** y activa **Explorador NPN**.

## Uso

1. Añade al proyecto la capa que contiene el NPN (u otro código en el campo).
2. Abre el panel **Explorador NPN** (barra de herramientas o menú *Complementos*).
3. Elige la **capa** y el **columna** (campo) a leer.
4. Pulsa **Sonda: activar**. El cursor pasa a modo cruz.
5. Mueve el ratón sobre las entidades: el **Valor NPN** se actualiza con el dato bajo el cursor.
6. **Doble clic** en el mapa o en el cuadro de valor **fija** el texto (fondo amarillo); un segundo doble clic lo libera y vuelve al modo en vivo. Desactivar la sonda o cambiar de capa/campo anula el fijado.
7. El botón con **icono de copiar** (junto al resultado) copia al portapapeles el NPN, los avisos de validación visibles y el desglose del análisis (texto plano).

## Análisis del No Predial (30 dígitos)

- El panel muestra, debajo de **Valor NPN**, el bloque **Resultado del análisis** con una fila por componente: Departamento, Municipio, Zona U/R, Sector, Comuna, Barrio, Vereda/Manzana, Terreno, Condición, Nº de edificio, Nº de piso, Unidad predial.
- Un código es **válido** si consta de **exactamente 30 caracteres, todos numéricos**. Los diccionarios de departamento y municipio, zonas y condiciones se leen de `npn_predial_reference.json`.

Mensajes habituales:

- **Vacío, nulo o no legible:** no hay valor interpretable; se informa que no corresponde a un número predial válido.
- **Texto con contenido pero no cumple 30 dígitos numéricos:** se muestra el aviso al respecto; el desglose queda en guiones.
- Con **NPN correcto** las celdas del desglose se muestran en color de éxito; el texto de cada fila se puede **seleccionar y copiar** con el ratón.

## Licencia

El proyecto incluye en la raíz el fichero [`LICENSE`](LICENSE) con el **texto completo de la GNU General Public License, versión 3** (29 de junio de 2007), tal como lo publica la [Free Software Foundation](https://www.fsf.org/) en [https://www.gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html).

