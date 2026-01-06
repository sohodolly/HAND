"""
Weather Forecasting System based on GLDAS
"""

import earthaccess
import netCDF4 as nc
import numpy as np
import pandas as pd
from prophet import Prophet
from datetime import datetime, timedelta
import os
import glob
import argparse
import warnings
import re
from pathlib import Path
warnings.filterwarnings('ignore')

class Config:
    GLDAS_SHORT_NAME = 'GLDAS_NOAH025_M'
    MIN_DATA_POINTS = 12
    MAX_DOWNLOAD_FILES = 200

def setup_argparse():
    parser = argparse.ArgumentParser(description='Weather forecasting based on GLDAS data')
    
    parser.add_argument('--lat', nargs=2, type=float, required=True, help='Latitude range (min max)')
    parser.add_argument('--lon', nargs=2, type=float, required=True, help='Longitude range (min max)')
    parser.add_argument('--target-date', type=str, required=True, help='Target date for forecast (YYYY-MM-DD)')
    parser.add_argument('--start', type=str, default='2000-01-01', help='Start date for data')
    parser.add_argument('--end', type=str, default='2024-12-31', help='End date for data')
    parser.add_argument('--region', type=str, default='Custom Region', help='Region name')
    parser.add_argument('--output-dir', type=str, default='./gldas_data', help='Data directory')
    parser.add_argument('--no-download', action='store_true', help='Do not download new data')
    parser.add_argument('--max-files', type=int, default=Config.MAX_DOWNLOAD_FILES, help='Maximum files to download')
    parser.add_argument('--use-existing', action='store_true', help='Use existing files without downloading new ones')
    
    return parser.parse_args()

def setup_earthdata_auth():
    try:
        auth = earthaccess.login(persist=True)
        if auth:
            print("✅ Earthdata authentication successful")
        return auth
    except Exception as e:
        print(f"❌ Earthdata authentication error: {e}")
        return False

def get_existing_files(output_dir):
    """Get list of existing GLDAS files"""
    nc_files = glob.glob(os.path.join(output_dir, "*.nc4"))
    nc_files.extend(glob.glob(os.path.join(output_dir, "*.nc")))
    return sorted(nc_files)

def download_gldas_data(args):
    """Download GLDAS data from server"""
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"📥 Searching GLDAS data from {args.start} to {args.end}...")
    
    try:
        results = earthaccess.search_data(
            short_name=Config.GLDAS_SHORT_NAME,
            temporal=(args.start, args.end),
            bounding_box=(args.lon[0], args.lat[0], args.lon[1], args.lat[1]),
            count=args.max_files
        )
        
        if len(results) == 0:
            print("❌ No GLDAS data found for specified parameters")
            return []
        
        print(f"📊 Found {len(results)} GLDAS files")
        
        # Check existing files
        existing_files = get_existing_files(args.output_dir)
        
        # If using only existing files
        if args.use_existing:
            if existing_files:
                print(f"🔍 Using {len(existing_files)} existing files")
                return existing_files
            else:
                print("❌ No existing files found but --use-existing specified")
                return []
        
        # If not downloading new data
        if args.no_download:
            if existing_files:
                print(f"🔍 Using {len(existing_files)} existing files (--no-download)")
                return existing_files
            else:
                print("❌ No existing files found")
                return []
        
        # Determine files to download
        files_to_download = []
        for result in results:
            filename = os.path.basename(result.data_links()[0])
            local_path = os.path.join(args.output_dir, filename)
            if not os.path.exists(local_path):
                files_to_download.append(result)
        
        if not files_to_download:
            print("✅ All files already downloaded")
            return existing_files
        
        print(f"⬇️ Downloading {len(files_to_download)} new files...")
        
        # Download files
        downloaded_files = earthaccess.download(files_to_download, args.output_dir)
        
        if hasattr(downloaded_files, '__len__'):
            print(f"✅ Successfully downloaded {len(downloaded_files)} files")
        else:
            print("✅ Download completed")
        
        # Get updated file list
        final_files = get_existing_files(args.output_dir)
        print(f"📁 Total {len(final_files)} files available")
        
        return final_files
        
    except Exception as e:
        print(f"❌ Data download error: {e}")
        return []

def extract_date_from_filename(filename):
    """Extract date from GLDAS filename"""
    try:
        patterns = [
            r'GLDAS_NOAH025_M\.A(\d{7})',
            r'GLDAS_NOAH025_M_(\d{6})',
            r'(\d{6})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                date_str = match.group(1)
                if len(date_str) == 6:
                    return datetime.strptime(date_str, '%Y%m')
                elif len(date_str) == 7:
                    year = int(date_str[:4])
                    day_of_year = int(date_str[4:7])
                    return datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
        
        return None
    except Exception:
        return None

def extract_weather_data(file_path, lat_range, lon_range):
    """Extract weather data from NetCDF file"""
    try:
        dataset = nc.Dataset(file_path, 'r')
        
        lats = dataset.variables['lat'][:] if 'lat' in dataset.variables else dataset.variables['latitude'][:]
        lons = dataset.variables['lon'][:] if 'lon' in dataset.variables else dataset.variables['longitude'][:]
        
        lat_mask = (lats >= lat_range[0]) & (lats <= lat_range[1])
        lon_mask = (lons >= lon_range[0]) & (lons <= lon_range[1])
        
        lat_idx = np.where(lat_mask)[0]
        lon_idx = np.where(lon_mask)[0]
        
        if len(lat_idx) == 0 or len(lon_idx) == 0:
            dataset.close()
            return None
        
        filename = os.path.basename(file_path)
        date = extract_date_from_filename(filename)
        
        if not date:
            dataset.close()
            return None
        
        data = {'date': date}
        
        if 'Rainf_f_tavg' in dataset.variables:
            rain = dataset.variables['Rainf_f_tavg'][0, lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1]
            data['precipitation'] = np.nanmean(rain) * 86400
        
        if 'Tair_f_inst' in dataset.variables:
            temp = dataset.variables['Tair_f_inst'][0, lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1]
            data['temperature'] = np.nanmean(temp) - 273.15
        
        if 'Qair_f_inst' in dataset.variables:
            humidity = dataset.variables['Qair_f_inst'][0, lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1]
            data['humidity'] = np.nanmean(humidity) * 100
        
        if 'Psurf_f_inst' in dataset.variables:
            pressure = dataset.variables['Psurf_f_inst'][0, lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1]
            data['pressure'] = np.nanmean(pressure) / 100
        
        if 'Wind_f_inst' in dataset.variables:
            wind = dataset.variables['Wind_f_inst'][0, lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1]
            data['wind_speed'] = np.nanmean(wind)
        
        if 'SWE_inst' in dataset.variables:
            snow = dataset.variables['SWE_inst'][0, lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1]
            data['snow_water'] = np.nanmean(snow)

        dataset.close()
        return data
        
    except Exception as e:
        return None

def process_all_files(file_list, lat_range, lon_range):
    """Process all files and create DataFrame"""
    print("🔍 Processing meteorological data...")
    data_list = []
    
    for i, file_path in enumerate(file_list):
        if i % 10 == 0:
            print(f"   Processed {i}/{len(file_list)} files...")
        
        data = extract_weather_data(file_path, lat_range, lon_range)
        if data:
            data_list.append(data)
    
    if not data_list:
        print("❌ Failed to process any files")
        return pd.DataFrame()
    
    df = pd.DataFrame(data_list)
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"✅ Successfully processed {len(df)} months of data")
    
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    df[numeric_columns] = df[numeric_columns].fillna(method='ffill')
    
    columns_to_keep = ['date', 'temperature', 'precipitation', 'humidity', 'pressure', 'wind_speed', 'snow_water']
    df = df[[col for col in columns_to_keep if col in df.columns]]
    
    return df

def prepare_prophet_data(df, target_column):
    """Prepare data for Prophet model"""
    if target_column not in df.columns:
        return None
    
    prophet_df = pd.DataFrame({
        'ds': df['date'],
        'y': df[target_column]
    })
    
    additional_features = ['temperature', 'humidity', 'pressure', 'wind_speed']
    for feature in additional_features:
        if feature in df.columns and feature != target_column:
            prophet_df[feature] = df[feature]
    
    return prophet_df.dropna()

def train_prophet_model(prophet_df):
    """Train Prophet model"""
    if prophet_df is None or len(prophet_df) < Config.MIN_DATA_POINTS:
        return None
    
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode='multiplicative',
        changepoint_prior_scale=0.05
    )
    
    feature_columns = [col for col in prophet_df.columns if col not in ['ds', 'y']]
    for feature in feature_columns:
        if pd.api.types.is_numeric_dtype(prophet_df[feature]):
            model.add_regressor(feature)
    
    try:
        model.fit(prophet_df)
        return model
    except Exception:
        return None

def make_forecast_for_date(model, df, target_date, target_column):
    """Make forecast for specific date"""
    if model is None:
        return None, None
    
    last_date = df['date'].max()
    target_datetime = datetime.strptime(target_date, '%Y-%m-%d')
    
    months_diff = (target_datetime.year - last_date.year) * 12 + (target_datetime.month - last_date.month)
    
    if months_diff <= 0:
        return None, None
    
    future = model.make_future_dataframe(periods=months_diff, freq='MS')
    
    feature_columns = [col for col in df.columns if col not in ['date', target_column]]
    
    for feature in feature_columns:
        if feature in df.columns and pd.api.types.is_numeric_dtype(df[feature]):
            try:
                monthly_data = df[df['date'].dt.month == target_datetime.month][feature]
                if len(monthly_data) > 0:
                    last_year_avg = monthly_data.mean()
                else:
                    last_year_avg = df[feature].tail(12).mean()
                
                future[feature] = last_year_avg
            except Exception:
                future[feature] = df[feature].iloc[-1]
    
    try:
        forecast = model.predict(future)
        target_month = target_datetime.replace(day=1)
        target_forecast = forecast[forecast['ds'] == target_month]
        
        if len(target_forecast) == 0:
            target_forecast = forecast.iloc[(forecast['ds'] - target_month).abs().argsort()[:1]]
        
        return forecast, target_forecast
        
    except Exception:
        return None, None

def calculate_wscore(forecasts):
    """Calculate WScore (Weather Comfort Score) from 1 to 5"""
    temp = forecasts.get('temperature', {}).get('value', 20)
    humidity = forecasts.get('humidity', {}).get('value', 50)
    wind = forecasts.get('wind_speed', {}).get('value', 3)
    precip = forecasts.get('precipitation', {}).get('value', 0)
    snow = forecasts.get('snow_water', {}).get('value', 0)
    
    score = 1
    
    # Temperature comfort
    if temp < -10 or temp > 35:
        score = max(score, 5)
    elif temp < -5 or temp > 30:
        score = max(score, 4)
    elif temp < 0 or temp > 25:
        score = max(score, 3)
    elif temp < 10 or temp > 20:
        score = max(score, 2)
    
    # Humidity
    if humidity > 85:
        score = max(score, 4)
    elif humidity > 70:
        score = max(score, 3)
    elif humidity < 20:
        score = max(score, 3)
    
    # Wind
    if wind > 15:
        score = max(score, 5)
    elif wind > 10:
        score = max(score, 4)
    elif wind > 7:
        score = max(score, 3)
    
    # Precipitation
    if precip > 200:
        score = max(score, 5)
    elif precip > 100:
        score = max(score, 4)
    elif precip > 50:
        score = max(score, 3)
    
    # Snow
    if snow > 200:
        score = max(score, 5)
    elif snow > 100:
        score = max(score, 4)
    elif snow > 50:
        score = max(score, 3)
    
    return min(score, 5)

def get_comfort_description(wscore, forecasts):
    """Get text description of weather comfort"""
    temp = forecasts.get('temperature', {}).get('value', 20)
    humidity = forecasts.get('humidity', {}).get('value', 50)
    wind = forecasts.get('wind_speed', {}).get('value', 3)
    
    descriptions = []
    
    # Temperature conditions
    if temp > 35:
        descriptions.append("🔥 VERY HOT conditions")
    elif temp > 30:
        descriptions.append("🌡️ Hot conditions")
    elif temp < -10:
        descriptions.append("❄️ VERY COLD conditions")
    elif temp < -5:
        descriptions.append("🥶 Cold conditions")
    
    # Wind
    if wind > 15:
        descriptions.append("💨 VERY WINDY conditions")
    elif wind > 10:
        descriptions.append("💨 Windy conditions")
    
    comfort_levels = {
        1: "😊 EXCELLENT - very comfortable conditions",
        2: "🙂 GOOD - comfortable conditions", 
        3: "😐 MODERATE - average comfort conditions",
        4: "😟 UNCOMFORTABLE - uncomfortable conditions",
        5: "😨 CRITICAL - very uncomfortable conditions"
    }
    
    main_description = comfort_levels.get(wscore, "😐 Moderate conditions")
    
    return main_description, descriptions

def analyze_weather_risks(forecasts, historical_data, target_date):
    """Analyze risks of dangerous weather phenomena"""
    risks = []
    
    precip_forecast = forecasts.get('precipitation', {}).get('value', 0)
    temp_forecast = forecasts.get('temperature', {}).get('value', 0)
    wind_forecast = forecasts.get('wind_speed', {}).get('value', 0)
    snow_forecast = forecasts.get('snow_water', {}).get('value', 0)
    
    # Flood risk
    if precip_forecast > 300:
        risks.append(("🔴 HIGH FLOOD RISK", 
                     "Extreme monthly precipitation - high flood probability"))
    elif precip_forecast > 150:
        risks.append(("🟡 MODERATE FLOOD RISK", 
                     "High monthly precipitation - possible local floods"))
    
    # Drought risk
    if precip_forecast < 20 and historical_data['precipitation'].tail(6).mean() < 30:
        risks.append(("🔴 DROUGHT RISK", 
                     "Long-term lack of precipitation - critically low levels"))
    elif precip_forecast < 40:
        risks.append(("🟡 PRECIPITATION DEFICIT", 
                     "Low precipitation - possible water supply issues"))
    
    # Frost risk
    if temp_forecast < -15:
        risks.append(("🔴 EXTREME FROST", 
                     "Dangerously low temperature - infrastructure risk"))
    elif temp_forecast < -5:
        risks.append(("🟡 STRONG FROST", 
                     "Low temperature - agriculture risk"))
    
    # Heat risk
    if temp_forecast > 35:
        risks.append(("🔴 EXTREME HEAT", 
                     "Dangerously high temperature - health risk"))
    elif temp_forecast > 30:
        risks.append(("🟡 HEAT", 
                     "High temperature - risk of overheating"))
    
    # Heavy snow risk
    if snow_forecast > 500:
        risks.append(("🔴 EXTREME SNOWFALL", 
                     "Massive snow cover - transportation disruptions"))
    elif snow_forecast > 200:
        risks.append(("🟡 HEAVY SNOWFALL", 
                     "Significant snowfall - possible complications"))
    
    # Strong wind risk
    if wind_forecast > 20:
        risks.append(("🔴 HURRICANE WINDS", 
                     "Extremely strong wind - dangerous!"))
    elif wind_forecast > 15:
        risks.append(("🟡 STRONG WIND", 
                     "Powerful wind gusts - be careful!"))
    
    return risks

def display_weather_widget(wscore, comfort_desc, specific_conditions, forecasts):
    """Display visual weather comfort widget"""
    print("\n" + "="*60)
    print("🌤️  WEATHER COMFORT")
    print("="*60)
    
    stars = "⭐" * wscore
    print(f"🏆 WScore: {wscore}/5 {stars}")
    print(f"📊 {comfort_desc}")
    
    if specific_conditions:
        print("\n🔍 SPECIFIC CONDITIONS:")
        for condition in specific_conditions:
            print(f"   • {condition}")
    
    print("\n📈 COMFORT DETAILS:")
    
    temp = forecasts.get('temperature', {}).get('value', 20)
    if temp > 30:
        print("   🌡️  Temperature: Hot (cooling needed)")
    elif temp > 20:
        print("   🌡️  Temperature: Comfortable")
    elif temp > 10:
        print("   🌡️  Temperature: Cool (light clothing)")
    elif temp > 0:
        print("   🌡️  Temperature: Cold (warm clothing)")
    else:
        print("   🌡️  Temperature: Very cold (winter clothing)")
    
    wind = forecasts.get('wind_speed', {}).get('value', 3)
    if wind > 15:
        print("   💨 Wind: Very strong (dangerous)")
    elif wind > 10:
        print("   💨 Wind: Strong (hard to walk)")
    elif wind > 5:
        print("   💨 Wind: Moderate (noticeable)")
    else:
        print("   💨 Wind: Light (comfortable)")

def main():
    args = setup_argparse()
    
    print("\n" + "="*60)
    print("🌤️  GLDAS WEATHER FORECASTING SYSTEM")
    print("="*60)
    print(f"📍 Region: {args.region}")
    print(f"📌 Coordinates: {args.lat[0]}-{args.lat[1]}°N, {args.lon[0]}-{args.lon[1]}°E")
    print(f"🎯 Target date: {args.target_date}")
    print(f"📅 Data period: {args.start} - {args.end}")
    print("="*60)
    
    try:
        if not setup_earthdata_auth():
            return
        
        files = []
        if not args.no_download:
            files = download_gldas_data(args)
            if not files:
                return
        else:
            files = get_existing_files(args.output_dir)
            if not files:
                return
        
        df = process_all_files(files, args.lat, args.lon)
        
        if df.empty or len(df) < Config.MIN_DATA_POINTS:
            print(f"❌ Insufficient data for analysis (minimum {Config.MIN_DATA_POINTS} months required)")
            return
        
        print(f"\n📊 Available data ({len(df)} months):")
        print(f"   Date range: {df['date'].min().strftime('%Y-%m')} - {df['date'].max().strftime('%Y-%m')}")
        
        print("\n📈 Creating forecasts...")
        forecasts = {}
        target_parameters = ['temperature', 'precipitation', 'wind_speed', 'humidity', 'snow_water']
        
        for param in target_parameters:
            if param in df.columns:
                print(f"   Forecasting {param}...")
                prophet_df = prepare_prophet_data(df, param)
                
                if prophet_df is not None and len(prophet_df) >= Config.MIN_DATA_POINTS:
                    model = train_prophet_model(prophet_df)
                    
                    if model is not None:
                        forecast, target_forecast = make_forecast_for_date(
                            model, df, args.target_date, param
                        )
                        
                        if forecast is not None and target_forecast is not None and len(target_forecast) > 0:
                            forecasts[param] = {
                                'value': target_forecast['yhat'].iloc[0],
                                'confidence_lower': target_forecast['yhat_lower'].iloc[0],
                                'confidence_upper': target_forecast['yhat_upper'].iloc[0]
                            }
        
        if not forecasts:
            print("❌ Failed to create any forecasts")
            return
        
        wscore = calculate_wscore(forecasts)
        comfort_desc, specific_conditions = get_comfort_description(wscore, forecasts)
        
        risks = analyze_weather_risks(forecasts, df, args.target_date)
        
        print("\n" + "="*60)
        print("📊 FORECAST RESULTS")
        print("="*60)
        for param, data in forecasts.items():
            value = data['value']
            unit = ""
            if param == 'temperature': unit = "°C"
            elif param == 'precipitation': unit = "mm/month"
            elif param == 'wind_speed': unit = "m/s"
            elif param == 'humidity': unit = "%"
            elif param == 'snow_water': unit = "kg/m²"
            
            print(f"🌡️  {param}: {value:.1f} {unit}")
        
        display_weather_widget(wscore, comfort_desc, specific_conditions, forecasts)
        
        if risks:
            print("\n" + "="*60)
            print("⚠️  WARNINGS AND RISKS")
            print("="*60)
            for risk, description in risks:
                print(f"{risk}")
                print(f"   {description}")
        else:
            print("\n✅ No significant weather risks detected")
        
        forecast_data = {}
        for param, data in forecasts.items():
            forecast_data[param] = data['value']
            forecast_data[f'{param}_lower'] = data.get('confidence_lower', data['value'])
            forecast_data[f'{param}_upper'] = data.get('confidence_upper', data['value'])
        
        forecast_data['wscore'] = wscore
        forecast_data['comfort_description'] = comfort_desc
        forecast_df = pd.DataFrame([forecast_data])
        forecast_filename = f'forecast_{args.region.replace(" ", "_")}_{args.target_date}.csv'
        forecast_df.to_csv(forecast_filename, index=False)
        print(f"\n💾 Results saved to: {forecast_filename}")
        
        print("\n" + "="*60)
        print("✅ FORECASTING COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Critical error: {e}")

if __name__ == "__main__":
    main()
