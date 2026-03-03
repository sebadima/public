# JustPaste Clone

Sistema minimale di pasteboard basato su **FastAPI** con worker asincrono per la generazione di **PDF** tramite Chromium headless. Progettato per girare su Ubuntu LTS senza dipendenze gonfie.

## 1. Requisiti di Sistema (Ubuntu)

Oltre a Python 3, è necessario Chromium per la conversione HTML -> PDF:

```bash
sudo apt update && sudo apt install chromium-browser -y