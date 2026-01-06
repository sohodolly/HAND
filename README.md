# HAND Weather Analytics - Installation Guide

Complete setup guide for deploying the HAND Weather Analytics system on any machine.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Steps](#installation-steps)
- [Running the Application](#running-the-application)
- [Testing the System](#testing-the-system)
- [Configuration Options](#configuration-options)
- [Troubleshooting](#troubleshooting)
- [Updating the System](#updating-the-system)
- [Production Deployment](#production-deployment)
- [Additional Resources](#additional-resources)

---

## Prerequisites

### System Requirements

- **OS**: Linux, macOS, or Windows 10/11
- **Python**: 3.8 or higher
- **RAM**: Minimum 4GB (8GB recommended)
- **Storage**: At least 10GB free space for data
- **Internet**: Stable connection for data downloads

### Required Accounts

- **NASA Earthdata Account** (free): [Register here](https://urs.earthdata.nasa.gov/users/new)

---

## Installation Steps

### 1. Install Python and Git

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y
```

#### macOS

```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and Git
brew install python git
```

#### Windows

1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check **"Add Python to PATH"**
3. Download Git from [git-scm.com](https://git-scm.com/download/win)
4. Install with default settings

---

### 2. Clone or Download the Project

#### Option A: Using Git (recommended)

```bash
git clone <your-repository-url>
cd hand-weather-analytics
```

#### Option B: Manual Download

1. Download project files
2. Extract to a folder
3. Open terminal/command prompt in that folder

---

### 3. Create Virtual Environment

This isolates project dependencies from your system Python.

#### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

#### Windows (Command Prompt)

```cmd
python -m venv venv
venv\Scripts\activate
```

#### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> **Note**: You should see `(venv)` before your command prompt when activated.

---

### 4. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, create it with this content:

```txt
Flask==3.0.0
earthaccess==0.8.2
netCDF4==1.6.5
numpy==1.24.3
pandas==2.0.3
prophet==1.1.5
werkzeug==3.0.1
```

Then run:

```bash
pip install -r requirements.txt
```

---

### 5. Setup NASA Earthdata Authentication

#### Create `.netrc` file for authentication

**Linux/macOS:**

```bash
cat > ~/.netrc << EOF
machine urs.earthdata.nasa.gov
login YOUR_USERNAME
password YOUR_PASSWORD
EOF

chmod 600 ~/.netrc
```

**Windows:**

Create file `C:\Users\YourUsername\.netrc` with content:

```
machine urs.earthdata.nasa.gov
login YOUR_USERNAME
password YOUR_PASSWORD
```

Replace `YOUR_USERNAME` and `YOUR_PASSWORD` with your NASA Earthdata credentials.

#### Alternative: Interactive Login

The system will prompt for credentials on first run if `.netrc` doesn't exist.

---

### 6. Create Required Directories

```bash
mkdir -p gldas_data
mkdir -p templates
```

---

### 7. Setup Project Structure

Ensure your project has this structure:

```
hand-weather-analytics/
├── app.py
├── predicts.py
├── index.html (move to templates/)
├── requirements.txt
├── SETUP.md
├── README.md
├── .gitignore
├── gldas_data/ (auto-created)
├── templates/
│   └── index.html
└── venv/
```

**Move index.html to templates folder:**

#### Linux/macOS

```bash
mv index.html templates/
```

#### Windows

```cmd
move index.html templates\
```

---

## Running the Application

### 1. Activate Virtual Environment

If not already active:

#### Linux/macOS

```bash
source venv/bin/activate
```

#### Windows

```cmd
venv\Scripts\activate
```

### 2. Start the Flask Server

```bash
python app.py
```

You should see:

```
 * Running on http://0.0.0.0:5000
 * Running on http://127.0.0.1:5000
```

### 3. Access the Application

Open your web browser and go to:

```
http://localhost:5000
```

---

## Testing the System

### 1. Test Data Download (Optional)

Test if data download works:

```bash
python predicts.py \
  --lat 50.0 51.0 \
  --lon 30.0 31.0 \
  --target-date 2025-03-01 \
  --region "Test Region" \
  --start 2023-01-01 \
  --end 2024-12-31
```

### 2. Use Web Interface

1. Open [http://localhost:5000](http://localhost:5000)
2. Click on map to select location (or use default Kyiv)
3. Select target date
4. Click **"GET FORECAST"**
5. Wait for processing (1-3 minutes)
6. View results with WScore

---

## Configuration Options

### Modify Data Directory

Edit `app.py` or use command line:

```bash
python predicts.py --output-dir /path/to/data ...
```

### Adjust Download Limits

Edit `predicts.py`:

```python
class Config:
    MAX_DOWNLOAD_FILES = 200  # Change this number
```

### Use Existing Data (Skip Downloads)

```bash
python predicts.py --no-download ...
```

---

## Troubleshooting

### Problem: "Module not found" errors

**Solution:**

```bash
pip install --upgrade -r requirements.txt
```

### Problem: Earthdata authentication fails

**Solution:**

1. Verify credentials at [NASA Earthdata](https://urs.earthdata.nasa.gov)
2. Check `.netrc` file permissions: `chmod 600 ~/.netrc`
3. Try interactive login by removing `.netrc`

### Problem: "No GLDAS data found"

**Solution:**

1. Check internet connection
2. Verify date range is valid (data available from 2000+)
3. Try wider geographical area
4. Check NASA Earthdata system status

### Problem: Port 5000 already in use

**Solution:**

Change port in `app.py`:

```python
app.run(debug=True, host='0.0.0.0', port=8080)
```

Then access: [http://localhost:8080](http://localhost:8080)

### Problem: Slow downloads

**Solution:**

1. Reduce `--max-files` parameter
2. Use `--no-download` with existing data
3. Check network speed
4. Try different time (NASA servers may be busy)

### Problem: Windows PowerShell script execution error

**Solution:**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Updating the System

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Update dependencies
pip install --upgrade -r requirements.txt

# Pull latest changes (if using git)
git pull
```

---

## Production Deployment

### Using Gunicorn (Linux/macOS)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Using Waitress (Windows)

```bash
pip install waitress
waitress-serve --listen=0.0.0.0:5000 app:app
```

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t hand-weather .
docker run -p 5000:5000 hand-weather
```

---

## Security Notes

1. **Never commit** `.netrc` or `.env` files to version control
2. Add to `.gitignore`:

```gitignore
.netrc
.env
venv/
gldas_data/
__pycache__/
*.pyc
*.csv
*.nc4
*.nc
.DS_Store
```

3. Use environment variables in production
4. Enable HTTPS in production deployment
5. Set `debug=False` in production

---

## Additional Resources

- [GLDAS Documentation](https://ldas.gsfc.nasa.gov/gldas)
- [NASA Earthdata](https://earthdata.nasa.gov)
- [Prophet Documentation](https://facebook.github.io/prophet)
- [Flask Documentation](https://flask.palletsprojects.com)

---

## Quick Start Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed
- [ ] NASA Earthdata account created
- [ ] `.netrc` file configured
- [ ] Project structure correct
- [ ] `gldas_data` directory exists
- [ ] Flask server starts without errors
- [ ] Web interface accessible at localhost:5000
- [ ] Test forecast completed successfully

---

## Getting Help

If you encounter issues:

1. Check this guide thoroughly
2. Review error messages carefully
3. Verify all prerequisites are met
4. Check NASA Earthdata system status
5. Ensure stable internet connection

---

## First Forecast Test

If you can access the web interface and generate forecasts, your installation is complete!

**Steps:**

1. Open [http://localhost:5000](http://localhost:5000)
2. Use default location (Kyiv) or select any location
3. Choose tomorrow's date
4. Click **"GET FORECAST"**
5. Wait 2-3 minutes for results

---

**Project Version**: 1.0.0  
**Last Updated**: 2025-01-05  
