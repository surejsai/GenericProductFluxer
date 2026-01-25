# Quick Start with Poetry

## ✅ Application is Running!

Your Flask application is now running at:
- **http://localhost:5000**
- **http://127.0.0.1:5000**

## 🚀 How to Use

### Start the Application
```bash
# From the project directory
poetry run python app.py
```

### Stop the Application
Press `CTRL+C` in the terminal where the app is running.

### Restart the Application
```bash
# Stop with CTRL+C, then run again
poetry run python app.py
```

## 📦 Dependencies Installed

All dependencies have been added to `pyproject.toml`:
- ✅ Flask (web framework)
- ✅ flask-cors (CORS support)
- ✅ requests (HTTP client)
- ✅ beautifulsoup4 (HTML parsing)
- ✅ python-dotenv (environment variables)
- ✅ google-search-results (SERP API)
- ✅ And all your existing dependencies

## 🎨 Using the Web Application

1. **Open your browser** to http://localhost:5000

2. **Page 1: Enter Query**
   - Type a product search query (e.g., "wireless headphones")
   - Click "Start Discovery"

3. **Page 2: Watch Progress**
   - See real-time loading indicators
   - Watch as products are found and extracted
   - ✓ Success / ✗ Error indicators

4. **Page 3: View Results**
   - Browse extracted product information
   - See confidence scores
   - Export results as JSON
   - Start new search

## 📁 Files Created

Your project now has these new files:
```
GenericProductFluxer/
├── app.py                    # Flask backend (NEW)
├── templates/
│   └── index.html           # Frontend UI (NEW)
├── pyproject.toml           # Updated with Flask deps
├── poetry.lock              # Updated
├── README.md                # Basic readme (NEW)
├── requirements.txt         # For non-Poetry users (NEW)
└── Documentation:
    ├── WEB_APP_README.md         # Complete docs (NEW)
    ├── QUICK_START.md            # Quick guide (NEW)
    ├── POETRY_QUICK_START.md     # This file (NEW)
    └── NEW_WEB_APP_SUMMARY.md    # Overview (NEW)
```

## 🔧 Poetry Commands

### Install dependencies
```bash
poetry install
```

### Add new dependency
```bash
poetry add package-name
```

### Update dependencies
```bash
poetry update
```

### Run Python scripts
```bash
poetry run python script.py
```

### Activate virtual environment
```bash
poetry shell
# Then you can run: python app.py
```

## 🌐 API Endpoints

The Flask app provides these endpoints:

### POST /api/search
Search for popular products
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"wireless headphones"}'
```

### POST /api/extract
Extract product description
```bash
curl -X POST http://localhost:5000/api/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/product"}'
```

### POST /api/extract-batch
Extract multiple products
```bash
curl -X POST http://localhost:5000/api/extract-batch \
  -H "Content-Type: application/json" \
  -d '{"products":[{"title":"Product","link":"https://..."}]}'
```

## 🎯 Application Flow

```
User Input (Page 1)
       ↓
   SERP API Search
       ↓
   Find Products
       ↓
   Show Progress (Page 2)
       ↓
   ScraperAPI Fetch HTML
       ↓
   NLP Extraction
       ↓
   Display Results (Page 3)
```

## ✨ Features

- ✅ **3-Page Flow**: Input → Progress → Results
- ✅ **Real-time Loading**: Watch extraction progress
- ✅ **Beautiful UI**: Luxury theme with animations
- ✅ **Neural Network Background**: Cursor-reactive
- ✅ **NLP Extraction**: Advanced semantic matching
- ✅ **Confidence Scores**: High/Medium/Low ratings
- ✅ **Auto-Retry**: Automatic JS rendering for blocked sites
- ✅ **Export**: Save results as JSON

## 🔑 Environment Variables

Make sure your `.env` file has:
```bash
SERP_API_KEY=d749d8335907f29a6aa3de6152ba4f6940cc3cab7a000b7a32f5e8908a0c7a3f
SCRAPER_API_KEY=2bfb9486a6b5d06a5e5c860b499fbbb9
```

## 🐛 Troubleshooting

### Port already in use
```bash
# Windows: Find and kill process
netstat -ano | findstr :5000
taskkill /PID <process_id> /F
```

### Module not found
```bash
# Reinstall dependencies
poetry install
```

### App won't start
```bash
# Check if Poetry environment is active
poetry env info

# Try running with poetry run
poetry run python app.py
```

### API errors
- Check `.env` file exists with valid API keys
- Verify `python-dotenv` is installed: `poetry show python-dotenv`
- Check SERP API and ScraperAPI dashboards for quota

## 📊 What Each Tool Does

| Tool | Purpose |
|------|---------|
| **SERP API** | Searches Google Shopping for products |
| **ScraperAPI** | Fetches HTML from product pages |
| **html_product_extractor.py** | Extracts descriptions with NLP |
| **Flask** | Web server for the application |
| **BeautifulSoup** | Parses HTML content |

## 💡 Tips

1. **Keep terminal open**: The app runs in the terminal
2. **Watch the logs**: See requests in real-time
3. **Debug mode is on**: Changes auto-reload (mostly)
4. **Use Poetry run**: Always prefix with `poetry run`
5. **Check localhost:5000**: That's your app URL

## 🎉 You're Ready!

Your application is running and ready to use:
- **URL**: http://localhost:5000
- **Status**: ✅ Running
- **Environment**: Poetry virtual environment
- **Mode**: Debug (development)

## 📚 More Help

- [WEB_APP_README.md](WEB_APP_README.md) - Complete technical docs
- [NEW_WEB_APP_SUMMARY.md](NEW_WEB_APP_SUMMARY.md) - What was built
- [QUICK_START.md](QUICK_START.md) - General quick start

---

**Enjoy your Fluxer Atelier application!** 🚀
