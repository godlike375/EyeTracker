## EyeTracker
Данный проект позволяет перемещать лазер за объектом (изначальная цель - глаз во время операции). Построен на архитектуре MVVM.
Разрабатывался на python 3.8

### Установка:

    git clone https://github.com/godlike375/EyeTracker.git
    
    cd EyeTracker
    
    python -m venv /venv
    
    venv_python -m pip install -r requirements.txt
    
    venv_python main.py

#### Если нужно запускать линтер при коммитах, то вставляем себе pre-commmit хук в .git с текстом:

    #!/bin/bash
    
    export PYTHONIOENCODING="utf-8"
    
    VENV_PYTHON="./venv_python.sh"
    
    "$VENV_PYTHON" -m flake8 ./model ./common ./view
    
    if [[ $? -ne 0 ]]; then
    
        exit 1
    
    fi 

### Компиляция приложения:

    venv_python -m pip install pyinstaller
    pyinstaller --noconsole --onefile --name eye_tracker --icon tracking.ico --add-data "alert.wav;." --add-data "tracking.ico;." main.py

