# MyPaste RAW - Control Logic
PYTHON = python3
PID_FILE = mypaste.pid
PORT = 5000
STORAGE = $(HOME)/justpaste

.PHONY: run stop status list

# Lancia il server. Nota: in foreground il PID_FILE non serve per il kill, 
# ma lo stop pulisce comunque il socket della porta PORT.
run: stop
	@mkdir -p $(STORAGE)
	@echo "[STARTING] MyPaste RAW Server on port $(PORT)..."
	$(PYTHON) main.py

# Forza la liberazione della porta e pulisce file residui
stop:
	@echo "[CLEANING] Killing processes on port $(PORT)..."
	-@fuser -k $(PORT)/tcp 2>/dev/null || true
	-@if [ -f $(PID_FILE) ]; then kill -9 $$(cat $(PID_FILE)) 2>/dev/null || true; fi
	-@rm -f $(PID_FILE)

# Elenca i paste. Se la cartella è vuota non crasha.
list:
	@echo "[STORAGE] Current saved pastes in $(STORAGE):"
	@ls -lh $(STORAGE) 2>/dev/null || echo "Empty or missing directory."

# Stato del socket (L4)
status:
	@lsof -i :$(PORT) || echo "Port $(PORT) is FREE"