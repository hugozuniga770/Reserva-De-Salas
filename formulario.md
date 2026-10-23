# Diccionario del formulario (atari.scz.upb.edu/student_reservation.php)

El formulario se envía por `POST` a la misma URL con estos campos:

| Campo         | Ejemplo               |
| :------------ | :-------------------- |
| `room`        | `8`                   |
| `first_name`  | `Hugo Rafael`         |
| `last_name`   | `Zúñiga Daza`         |
| `code`        | `95503`               |
| `schedule`    | `12:15-14:15`         |
| `purpose`     | `Estudio académico`   |

## Salas (`room` → variable `UPB_SALAS`)

| Sala              | ID   |
| :---------------- | :--- |
| Sala de estudio B | `15` |
| Sala de estudio C | `3`  |
| Sala de estudio D | `6`  |
| Sala de estudio F | `8`  |
| Sala de estudio G | `9`  |
| Sala de estudio H | `14` |
| Sala de lectura A | `10` |
| Sala de lectura D | `13` |

## Horarios (`schedule` → variable `UPB_HORARIO`)

El servidor usa el texto del horario sin cero inicial. Los `id` de los radio
buttons (`slot_…`) son simplemente el MD5 de ese texto, por eso no cambian.

| Bloque        | `schedule`     | id del radio                              |
| :------------ | :------------- | :---------------------------------------- |
| 07:45 – 09:45 | `7:45-9:45`    | `slot_94b8b48865360042a741a450c6441be0`   |
| 10:00 – 12:00 | `10:00-12:00`  | `slot_cc9dc7dfdbf99c1d42f944c656c62e4d`   |
| 12:15 – 14:15 | `12:15-14:15`  | `slot_b0030e1d389405aae784568ad8e26553`   |
| 14:30 – 16:30 | `14:30-16:30`  | `slot_fc5e47c4011ddab1419ef6e9da33154c`   |
| 16:45 – 18:45 | `16:45-18:45`  | `slot_e7a3d271d18d86dc1ab2bca33b63f319`   |
| 19:00 – 21:00 | `19:00-21:00`  | `slot_e93ad1f8c976ce25fcaaa7539e2233dd`   |

## De dónde sale la disponibilidad

La página trae dentro de un `<script>`:

- `const occupied = {"8": {"12:15-14:15": true, ...}, ...}` → qué está ocupado por sala.
- `events: [{"title": "Nombre Apellido — Sala", "extendedProps": {"slot": "...", "room": "..."}}]`
  → el calendario; es lo que el bot usa para **confirmar** que la reserva es tuya.
- `const today = 'AAAA-MM-DD'` → la fecha del servidor (cambia a las 20:00 hora Bolivia).

Los mensajes de resultado vienen como `.alert-success` / `.alert-danger`.
