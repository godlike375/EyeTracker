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


### Реализованные фунции приложения:
#### Автоматические:
    Сохранение и загрузка всех настроек
    Сохранение и загрузка выделенной области
    Ведение журналов о событиях программы
    Калибровка координатной системы
    Калибровка шумоподавления камеры
    Калибровка лазера
    Обнаружение устройства контроллера лазера
    Обнаружение камеры
    Подтверждения действий пользователя
    Ограничения некорректного использования программы
    Перезагрузка программы
    Расчёт перемещения лазера в соответствии с координатами объекта на экране
    Подача звукового сигнала при выходе объекта за границы
    Обнаружение и исправление критических ошибок во время работы программы
    Компактное расположение элементов графического интерфейса
    Система подсказок по текущим действиям
    Шкала прогресса в режимах калибровки
    Упаковка программы в один файл и отсутствие необходимости установки
    Экономия и перераспределение ресурсов для улучшения качества трекинга
    Проверка введённых значений и подсказки по ожидаемому вводу

#### Ручные:
    Выделение объекта
    Прерывание процесса калибровки или выделения
    Позиционирование лазера
    Поворот изображения с камеры
    Отражение изображения с камеры
    Настройки производительности программы
    Настройки качества слежения за целью
    Дополнительные кнопки в меню настроек
    Выбор цвета отрисовки линий
