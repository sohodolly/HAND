from flask import Flask, render_template, request, jsonify
import subprocess
import os
import json
import shlex
from datetime import datetime
import glob
import pandas as pd

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/forecast', methods=['POST'])
def api_forecast():
    try:
        data = request.get_json()
        
        # Перевірка обов'язкових полів
        required_fields = ['lat_min', 'lat_max', 'lon_min', 'lon_max', 'target_date', 'region']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        # Будую команду для predicts.py
        cmd = [
            'python3', 'predicts.py',
            '--lat', str(data['lat_min']), str(data['lat_max']),
            '--lon', str(data['lon_min']), str(data['lon_max']),
            '--target-date', data['target_date'],
            '--region', data['region'],
            '--start', data.get('start_date', '2020-01-01'),
            '--end', data.get('end_date', datetime.now().strftime('%Y-%m-%d')),
            '--no-download'
        ]
        
        print(f"🔧 Виконується команда: {' '.join(cmd)}")
        
        # Виконуємо predicts.py і зберігаємо вивід
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if process.returncode == 0:
            # Успішне виконання
            output = process.stdout
            
            # Спочатку пробуємо прочитати CSV-файл
            csv_data = parse_csv_forecast(data['region'], data['target_date'])
            
            if csv_data:
                # Якщо CSV знайдено, використовуємо його
                metrics = calculate_metrics(csv_data)
                print(f"✅ Дані отримано з CSV: {csv_data['csv_file']}")
            else:
                # Інакше парсимо консольний вивід
                parsed_data = parse_output(output)
                metrics = calculate_metrics(parsed_data)
                print("⚠️ CSV не знайдено, використовуємо парсинг консолі")
            
            return jsonify({
                'success': True,
                'data': metrics,  # Стара структура - 'data'
                'console_output': output,
                'raw_output': output,
                'source': 'csv' if csv_data else 'console'
            })
        else:
            # Помилка виконання
            return jsonify({
                'success': False,
                'error': process.stderr,
                'console_output': process.stdout + "\n\n" + process.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False, 
            'error': 'Timeout: Процес завис',
            'console_output': 'Перевищено час очікування (300 секунд)'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e),
            'console_output': f'Помилка: {str(e)}'
        }), 500

def parse_csv_forecast(region, target_date):
    """
    Читає CSV-файл з прогнозом, створений predicts.py
    Тепер включає WScore
    """
    import pandas as pd
    import glob
    
    # Формуємо ім'я файлу
    safe_region = region.replace(" ", "_").replace(",", "")
    filename_pattern = f'forecast_{safe_region}_{target_date}.csv'
    
    # Шукаємо файл
    csv_files = glob.glob(filename_pattern)
    if not csv_files:
        csv_files = glob.glob('forecast_*.csv')
        if csv_files:
            csv_files.sort(key=os.path.getmtime, reverse=True)
            csv_file = csv_files[0]
            print(f"🔍 Використовуємо останній CSV файл: {csv_file}")
        else:
            print("❌ CSV файли не знайдено")
            return None
    else:
        csv_file = csv_files[0]
        print(f"✅ Знайдено CSV файл: {csv_file}")
    
    try:
        df = pd.read_csv(csv_file)
        print(f"📊 Колонки в CSV: {list(df.columns)}")
        
        if len(df) > 0:
            row = df.iloc[0]
            
            # Отримуємо всі доступні поля
            result = {
                'temperature': float(row.get('temperature', 0)),
                'precipitation': float(row.get('precipitation', 0)),
                'wind_speed': float(row.get('wind_speed', 0)),
                'humidity': float(row.get('humidity', 0)),
                'snow_water': float(row.get('snow_water', 0)),
                'pressure': float(row.get('pressure', 0)) if 'pressure' in row else 1013.25,
                'csv_file': csv_file
            }
            
            # Додаємо WScore якщо він є
            if 'wscore' in row:
                result['wscore'] = float(row['wscore'])
                print(f"✅ WScore знайдено: {row['wscore']}")
            
            # Додаємо comfort_description якщо він є
            if 'comfort_description' in row:
                result['comfort_description'] = str(row['comfort_description'])
                print(f"✅ Comfort description: {row['comfort_description']}")

            print(f"📋 Отримані дані з CSV: { {k: v for k, v in result.items() if k != 'csv_file'} }")
            return result
            
    except Exception as e:
        print(f"❌ Помилка читання CSV: {e}")
        return None
    
    return None

def parse_output(output):
    """
    Парсить вивід predicts.py для витягу даних про погоду
    """
    lines = output.split('\n')
    data = {}
    
    for line in lines:
        if ':' in line and '===' not in line and 'РИЗИК' not in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                
                # Вилучаємо одиниці виміру
                for unit in ['°C', 'mm/day', 'm/s', '%', 'kg/m²']:
                    value = value.replace(unit, '').strip()
                
                # Пропускаємо рядки з довірчим інтервалом
                if 'Довірчий інтервал' in key:
                    continue
                
                # Конвертуємо в число
                try:
                    data[key] = float(value)
                except:
                    data[key] = value
    
    return data

def calculate_metrics(data):
    """
    Розраховує метрики для віджетів на основі даних
    Тепер включає WScore
    """
    temp = float(data.get('temperature', 0))
    wind = float(data.get('wind_speed', 0))
    humidity = float(data.get('humidity', 0))
    precip = float(data.get('precipitation', 0))
    
    print(f"📊 Розрахунок метрик:")
    print(f"  Температура: {temp}°C")
    print(f"  Вітер: {wind} m/s ({wind * 3.6:.1f} km/h)")
    print(f"  Вологість: {humidity}%")
    print(f"  Опади: {precip} mm/day")
    
    # Стара структура метрик
    result = {
        'temperature': round(temp, 1),
        'precipitation': round(precip, 1),
        'wind_speed': round(wind, 1),
        'wind_speed_kmh': round(wind * 3.6, 1),
        'humidity': round(humidity, 1),
        'confidence': 85.5
    }
    
    # Додаємо WScore до старої структури якщо він є
    if 'wscore' in data:
        result['wscore'] = round(float(data['wscore']), 1)
        print(f"  🎯 WScore: {data['wscore']}")
    
    # Додаємо comfort_description якщо він є
    if 'comfort_description' in data:
        result['comfort_description'] = data['comfort_description']
        print(f"  📝 Comfort: {data['comfort_description']}")

    if 'specific_conditions' in data:
        result['specific_conditions'] = data['specific_conditions']
    
    # Старі розрахунки відсотків
    # Спека: якщо температура > 30°C
    if temp > 30:
        hot_perc = min(100, (temp - 30) * 10)
    elif temp > 20:
        hot_perc = (temp - 20) * 5
    else:
        hot_perc = 0
    
    # Холод: якщо температура < 0°C
    if temp < 0:
        cool_perc = min(100, abs(temp) * 10)
    elif temp < 10:
        cool_perc = (10 - temp) * 3
    else:
        cool_perc = 0
    
    # Вітер: конвертуємо m/s в km/h і перевіряємо > 30 km/h
    wind_kmh = wind * 3.6
    if wind_kmh > 30:
        wind_perc = min(100, (wind_kmh - 30) * 3)
    elif wind_kmh > 20:
        wind_perc = (wind_kmh - 20) * 2
    else:
        wind_perc = 0
    
    # Вологість: якщо > 80%
    if humidity > 80:
        humid_perc = min(100, (humidity - 80) * 5)
    elif humidity > 60:
        humid_perc = (humidity - 60) * 2
    else:
        humid_perc = 0
    
    # Додаємо старі відсотки
    result.update({
        'hot_perc': round(hot_perc, 1),
        'cool_perc': round(cool_perc, 1),
        'wind_perc': round(wind_perc, 1),
        'humid_perc': round(humid_perc, 1),
        'max_temp': round(temp + 5, 1)
    })
    
    print(f"  🔥 Спека: {hot_perc:.1f}%")
    print(f"  ❄️ Холод: {cool_perc:.1f}%")
    print(f"  💨 Вітер: {wind_perc:.1f}%")
    print(f"  💧 Вологість: {humid_perc:.1f}%")
    
    return result

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
