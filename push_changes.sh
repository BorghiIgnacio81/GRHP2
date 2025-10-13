#!/bin/bash

# Script para hacer push de los cambios al repositorio remoto
# Ejecutar como: bash push_changes.sh

# Configurar credenciales de Git si es necesario
# git config --global user.email "tu_email@ejemplo.com"
# git config --global user.name "Tu Nombre"

# Asegurar que estamos en la rama correcta
git checkout wip/server-fixes-2025-09-18

# Push de los cambios
git push -u origin wip/server-fixes-2025-09-18

echo "Push completado con éxito"