# 07 · Pruebas y trazabilidad

| Campo | Valor |
| :-- | :-- |
| Proyecto | Bot de Reserva de Salas UPB |
| Documento | Plan de pruebas y matriz de trazabilidad |
| Versión | 1.1 |
| Fecha | 07/11/2026 |
| Responsable | Hugo Rafael Zúñiga Daza |
| Revisado por | *(pendiente)* |
| Estado | Borrador para revisión |

> Redactado con asistencia de Claude (Anthropic).

## 1. Estrategia

| Nivel | Qué cubre | Archivo | Cantidad |
| :-- | :-- | :-- | :--: |
| Unitarias e integración | Bot contra un servidor falso que imita la página real (incluido el HTML guardado), con escenarios de fallo, y validación de los workflows (YAML como GitHub + actionlint) | `tests/test_reserva_bot.py` | 50 casos |
| Tickets y cifrado | Corridas aisladas, despacho, privacidad, compatibilidad navegador ↔ bot (Node ejecuta `docs/cifrado.js`) y bot completo por HTTP con las variables de Actions | `tests/test_solicitudes.py` | 37 casos |
| De punta a punta | Panel en Chromium real (390×844) con una API de GitHub simulada que rechaza entradas inválidas | `tests/panel_e2e.py` | 10 verificaciones |

Todas corren en GitHub Actions en cada push (`tests.yml`). El trabajo del panel sube las capturas como artefacto.

```bash
pip install -r requirements.txt pytest
python -m pytest -q                       # 87 casos
pip install playwright && python -m playwright install chromium
python tests/panel_e2e.py capturas        # 10 verificaciones + capturas
```

Las pruebas que dependen del tiempo usan un reloj inyectado (`Config.reloj`) y ritmos de milisegundos, así que corren en segundos.

**Contraprueba obligatoria**: las pruebas de reglas («no hace X») se revisaron también quitando la regla, para confirmar que fallan por la razón correcta. Así se detectó y corrigió una prueba de prioridad que pasaba por un motivo equivocado.

## 2. Matriz de trazabilidad

| Criterio | Requisito | Prueba(s) | Estado |
| :-- | :-- | :-- | :--: |
| CA-01.1 Éxito sin calendario no cuenta | RF-02 | `test_FALSO_POSITIVO_servidor_dice_exito_pero_no_guarda` | ✅ |
| CA-01.2 Conexión cortada: verifica y no duplica | RF-02 | `test_conexion_cortada_pero_reserva_entro_se_detecta` | ✅ |
| CA-01.3 Carrera perdida no es éxito | RF-02 | `test_carrera_perdida_no_es_exito` | ✅ |
| Reserva normal y campos del formulario | RF-01 | `test_reserva_normal_se_confirma`, `test_parsea_pagina_real_guardada`, `test_ids_del_formulario_son_md5_del_horario` | ✅ |
| CA-02.1 Respaldo en orden F→D→B→C | RF-03 | `test_orden_preferido_f_d_b_c_solo_salas_de_estudio`, `test_salas_de_respaldo_en_orden` | ✅ |
| CA-02.2 Solo salas de estudio | RF-03 | `test_salas_por_defecto_desde_entorno_es_fdbc_sin_lectura`, `test_ticket_solo_salas_de_estudio` | ✅ |
| CA-02.3 Sala del servicio no disponible | RF-14 | `test_nadie_puede_pedir_la_sala_del_servicio_en_su_horario`, `test_si_pide_f_y_otras_se_quita_la_f`, `test_la_f_en_otro_horario_si_se_puede`, `test_en_plena_apertura_un_ticket_nunca_intenta_la_sala_del_servicio`, `panel_e2e: plazos_y_bloqueo` | ✅ |
| Ventanas de vigilancia | RF-04 | `test_nucleo_y_banda_de_apertura`, `test_espera_la_apertura_de_las_20_y_reserva_el_dia_siguiente` | ✅ |
| CA-03.1 Fin por reloj | RF-05 | `test_fin_por_reloj_no_depende_de_la_hora_de_arranque`, `test_workflow_bien_configurado` | ✅ |
| CA-03.2 Arranque tardío avisa | RF-05, RF-06 | `test_arranque_tardio_sin_reserva_avisa_y_termina_en_rojo`, `test_arranque_tardio_igual_toma_una_sala_si_esta_libre` | ✅ |
| CA-03.3 Alerta roja y «Arrancarlo ahora» | RF-07 | `panel_e2e: arrancar_desde_alerta` | ✅ |
| CA-04.2 Ajustes → Variables | RF-08, RF-09 | `panel_e2e: ajustes` | ✅ |
| CA-05.1 Navegador cifra, bot descifra | RNF-02 | `test_cifrado_del_navegador_lo_lee_el_bot_y_viceversa`, `panel_e2e: cifrado_pagina_a_bot`, `panel_e2e: llave_desde_telefono` | ✅ |
| CA-05.2 Nada personal en público | RNF-02 | `test_ticket_oculta_los_datos_en_los_logs_publicos`, `test_ticket_con_codigo_invalido_no_expone_el_dato`, `test_workflow_tickets_en_carriles_propios` | ✅ |
| CA-05.3 Borrado tras usar | RF-12 | `test_ticket_reserva_solo_a_su_persona_y_borra_los_datos`, `test_ticket_ilegible_se_descarta_y_borra` | ✅ |
| CA-05.4 Estado por referencia | RF-13 | `panel_e2e: estado_publico` | ✅ |
| CA-06.1 Auto-aprobación a las 18:30 | RF-11 | `test_pendiente_antes_de_las_18_30_no_se_lanza`, `test_pendiente_se_lanza_sola_despues_de_las_18_30`, `test_auto_aprobacion_apagada` | ✅ |
| CA-06.2 Rechazadas y en curso no se relanzan | RF-11 | `test_rechazados_y_en_curso_no_se_relanzan`, `test_ticket_rechazado_no_reserva` | ✅ |
| CA-06.3 Pedidos con anticipación | RF-10 | `test_pedidos_con_semanas_de_anticipacion`, `test_ticket_de_otro_dia_espera_sin_tocar_nada` | ✅ |
| CA-06.4 Eliminar una no afecta a otras | RF-12 | `test_tickets_no_se_mezclan_entre_corridas`, `test_ticket_eliminado_termina_sin_hacer_nada` | ✅ |
| Aislamiento: tu corrida no reserva por otros | RF-12 | `test_tu_corrida_nunca_reserva_para_otros`, `test_despacho_solo_enruta_numeros_sin_descifrar` | ✅ |
| Tope por noche | RF-15 | `test_cupo_por_noche` | ✅ |
| Ritmo acotado | RNF-01 | `test_defaults_de_ritmo_no_son_de_flood` | ✅ |
| Red inestable | RNF-04 | `test_backoff_mas_corto_dentro_de_la_banda`, `test_sitio_caido`, `test_pagina_rota_nunca_envia` | ✅ |
| Acciones del administrador | RF-11 | `panel_e2e: acciones_admin` | ✅ |
| Carriles paralelos de tickets | RF-12 | `test_workflow_tickets_en_carriles_propios` | ✅ |
| Workflow válido tal como lo lee GitHub (C-10) | RNF-06 | `test_workflows_expresiones_cerradas_tras_leer_el_yaml`, `test_workflows_pasan_actionlint` | ✅ |
| Ticket aprobado de noche no se cierra sin vigilar (C-11) | RF-12 | `test_ticket_aprobado_de_noche_no_se_cierra_sin_vigilar`, `test_ticket_lanzado_de_noche_con_minutos_vigila_cancelaciones` | ✅ |
| Corrida activa sobre la de la cola (C-12) | RF-07 | `panel_e2e: corriendo_vs_en_cola` | ✅ |
| Bot completo por HTTP como en Actions | RF-01, RF-12 | `test_corrida_de_ticket_completa_por_http`, `test_tu_corrida_lanza_tickets_por_http` | ✅ |
| CA-07.1 y CA-07.2 Plazos, cuenta regresiva y marcas | RF-16 | `panel_e2e: plazos_y_bloqueo`, `panel_e2e: cifrado_pagina_a_bot` (exige confirmar el día sin garantía) | ✅ |
| CA-07.3 Cierre explica que llegó tarde | RF-16 | `test_sin_sala_por_llegar_tarde_lo_explica` | ✅ |
| Configuración pública sin nombres (`servicio.json`) | RF-14, RF-16 | `panel_e2e: ajustes` | ✅ |
| CA-08.1 Candado de repositorio | RF-17 | `test_el_bot_no_corre_en_copias_del_repositorio`, `test_el_bot_si_corre_en_el_repositorio_original`, `test_workflow_con_candado_al_repositorio_original` | ✅ |
| CA-08.2 Candado de dominio | RF-17 | `panel_e2e: copia_no_autorizada` | ✅ |
| CA-08.3 Licencia | RF-17 | `test_hay_licencia_con_todos_los_derechos_reservados` | ✅ |
| CA-04.3 Resultado de tu corrida | RF-07 | `test_resultado_reservada`, `test_resultado_ya_la_tenia`, `test_resultado_no_se_libero`, `test_resultado_prueba`, `test_resultado_horario_pasado`, `test_resultado_arranco_tarde`, `test_resultado_error_por_rechazos_y_sitio_caido`, `test_resultado_copia_no_autorizada` | ✅ |
| CA-04.3 Resultado de la corrida de un ticket | RF-07, RF-12 | `test_resultado_ticket_reservada`, `test_resultado_ticket_descartada_e_inactivo`, `test_resultado_ticket_pendiente_de_noche`, `test_resultado_ticket_sin_sala` | ✅ |
| CA-04.4 Bot, workflow y panel sincronizados | RF-07 | `test_workflow_muestra_cada_resultado` | ✅ |
| CA-04.3 y CA-04.5 en el panel | RF-07 | `panel_e2e: resultado_de_cada_corrida` | ✅ |

## 3. Pendiente de verificación manual

Estos puntos **no pueden** cubrirse con pruebas automáticas desde fuera de la red de la UPB:

| ID | Qué verificar | Cómo | Estado |
| :-- | :-- | :-- | :--: |
| VM-01 | Primera reserva real con verificación | Dry-run, luego una noche real; revisar el resumen | Pendiente |
| VM-02 | Hora real de apertura (SUP-01) | Línea «📅 El servidor cambió…» en el resumen | Pendiente |
| VM-03 | Mensajes reales de rechazo del sistema | Registro de la corrida | Pendiente |
| VM-04 | Panel contra la API real de GitHub | Guía → paso 2 «Revisar permisos» y paso 8 | Parcial: lectura, llave y descifrado verificados el 05/11; lanzar corridas tras C-10 |
| VM-05 | Carga del logo oficial desde GitHub Pages | Abrir el panel en el celular | ✅ Verificado el 05/11 |
| VM-07 | Primera solicitud real cifrada en el navegador y leída en el panel | Ticket #1 | ✅ Verificado el 05/11 |
| VM-06 | Corridas de tickets en paralelo (sin «queued») | Aprobar 2 solicitudes de prueba y mirar Actions | Pendiente |
