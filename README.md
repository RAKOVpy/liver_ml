# Приложение для обработки медицинских изображений

## Обзор

Это приложение предназначено для обработки медицинских изображений в формате DICOM с фокусом на сегментацию и аннотацию печени. Оно предоставляет удобный редактор изображений, который позволяет пользователям точно уточнять сегментации и аннотации непосредственно на изображениях. Обработанные и аннотированные изображения могут быть экспортированы для дальнейшего использования, включая дообучение моделей и анализ.

### Основные функции:
- Автоматическая сегментация печени на медицинских изображениях в формате DICOM.
- Интерактивный редактор изображений для добавления и корректировки аннотаций.
- Возможность отправки аннотированных данных для дообучения модели.
- Экспорт аннотированных изображений в различные форматы.

## Стек технологий

- **Backend**: 
  - Django 4.2.13
  - Python 3.10
  - MedPy, pydicom, SimpleITK для обработки медицинских изображений
  - Matplotlib, numpy, scipy для работы с изображениями
  - PyYAML для работы с конфигурационными файлами
  - torch для машинного обучения

- **Frontend**:
  - HTML5, CSS3
  - JavaScript (для взаимодействия с канвасом и отправки данных на сервер)

- **Дополнительные библиотеки**:
  - Albumentations для аугментации данных
  - OpenCV для обработки изображений
  
## Установка

Для установки и запуска приложения выполните следующие шаги:

### 1. Клонирование репозитория

Сначала клонируйте репозиторий:

```bash
    git clone https://github.com/RAKOVpy/liver_ml.git
    cd ./liver_ml/
```
### 2. Установка зависимостей
Создайте и активируйте виртуальное окружение:

```bash
    python -m venv venv
    source venv/bin/activate  # Для Linux/MacOS
    venv\Scripts\activate     # Для Windows
```
Установите все необходимые зависимости:

```bash
    pip install -r requirements.txt
```

### 3. Запуск приложения
Запустите сервер разработки:
```bash
    python manage.py runserver
```
Приложение будет доступно по адресу: http://127.0.0.1:8000/.

## Запуск в Docker
Если вы хотите запустить приложение в контейнере Docker, выполните следующие шаги:

### 1. Скачивание образа с Docker Hub
Приложение доступно на Docker Hub. Для того чтобы скачать образ и запустить его в контейнере, выполните следующие команды:
```bash
    docker pull remxd/liver:latest
```

### 2. Запуск контейнера
После того как образ будет загружен, вы можете запустить контейнер с помощью следующей команды:
```bash
    docker run -d -p 8000:8000 remxd/liver:latest
```
Это запустит контейнер и пробросит порт 8000 из контейнера на локальный хост, так что приложение будет доступно по адресу http://localhost:8000.
