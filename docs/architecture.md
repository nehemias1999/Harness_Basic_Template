# Arquitectura — Qué significa "hacer un buen trabajo" en <TU_PROYECTO>

> **Este archivo es una plantilla: rellénalo antes de escribir la primera feature.**
> Es el documento contra el que el agente revisor evalúa el código. Si un
> requisito no está aquí, no es un requisito — y el reviewer no lo exigirá.
> Sé concreto: "capas claras" no sirve, "solo estas tres capas, con estos
> nombres" sí.

## Principios

1. **Capas claras.** El proyecto tiene estas capas y solo estas:
   - `<modulo_1>.py` — <responsabilidad>
   - `<modulo_2>.py` — <responsabilidad>
   - `<modulo_3>.py` — <responsabilidad>

   No introducir capas adicionales (servicios, repositorios, ORMs) hasta que
   haya una razón concreta documentada como feature en `feature_list.json`.

2. **Sin dependencias externas.** Solo stdlib de Python. Si una feature
   requiere una dependencia, no se instala por iniciativa propia: se pasa la
   feature a estado `blocked` y se discute.

3. **Errores explícitos.** Las funciones que pueden fallar lanzan excepciones
   nombradas del dominio, no devuelven `None` ni un valor centinela.

4. **Inmutabilidad por defecto.** Las estructuras de datos del dominio son
   `@dataclass(frozen=True)`. Modificar = crear una instancia nueva.

5. **Atomicidad en disco.** Toda escritura de un archivo de estado se hace
   primero en un temporal y luego `os.replace()`. Nunca dejar un archivo a
   medio escribir.

<!-- Los principios 2-5 son transversales y suelen valer tal cual. El 1 y el
     flujo de datos son específicos de tu proyecto: reescríbelos. -->

## Flujo de datos

```
<entrada>  ─→  <modulo_3>.py (interfaz)
                 │
                 ├─ construye <entidad> con <modulo_2>.<constructor>(...)
                 │
                 └─→  <modulo_1>.load() / <modulo_1>.save()
                          │
                          └─→  <archivo de estado>
```

## Qué NO hacer

- No usar `print()` para errores. Usa `sys.stderr` y exit code != 0.
- No mezclar IO con lógica de dominio.
- No leer/escribir el archivo de estado dentro de un bucle: carga al inicio,
  modifica en memoria, guarda al final.
- No añadir un sistema de configuración. Las rutas se pasan explícitamente o
  usan una constante por defecto del módulo.
- <añade aquí los antipatrones concretos de tu dominio>
