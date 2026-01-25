# Quick Start Guide - Fluxer Atelier

## 🚀 Get Started in 3 Steps

### 1. Install Dependencies
```bash
pip install Flask flask-cors google-search-results python-dotenv
```

### 2. Set API Keys
Create/update your `.env` file:
```bash
SERP_API_KEY=d749d8335907f29a6aa3de6152ba4f6940cc3cab7a000b7a32f5e8908a0c7a3f
SCRAPER_API_KEY=2bfb9486a6b5d06a5e5c860b499fbbb9
```

### 3. Run the App
```bash
python app.py
```

Then open in your browser:
```
http://localhost:5000
```

## 📱 How to Use

### Page 1: Search
1. Enter a product query (e.g., "wireless headphones")
2. Click "Start Discovery"

### Page 2: Processing
- Watch real-time progress as the app:
  - Searches for popular products
  - Fetches product URLs
  - Extracts descriptions using AI/NLP

### Page 3: Results
- View extracted product information:
  - Product titles
  - Meta descriptions
  - Full product descriptions
  - Confidence scores
  - Extraction methods
- Export results as JSON
- Start a new search

## 🎨 Features

✅ **Beautiful luxury-themed UI**
✅ **Animated neural network background**
✅ **Real-time loading progress**
✅ **Intelligent NLP extraction**
✅ **Confidence scoring**
✅ **Auto-retry with JS rendering**
✅ **Export to JSON**
✅ **Mobile responsive**

## 🔧 Troubleshooting

### App won't start
```bash
# Check if ports are in use
netstat -ano | findstr :5000

# Kill process if needed
taskkill /PID <pid> /F
```

### API key errors
- Make sure `.env` file exists in project root
- Verify keys are correct (no quotes needed)
- Check `python-dotenv` is installed

### No products found
- Verify `SERP_API_KEY` is valid
- Check SERP API dashboard for quota
- Try a different search query

### Descriptions not extracting
- Verify `SCRAPER_API_KEY` is valid
- Check ScraperAPI dashboard for quota
- Some sites may have bot protection (app will auto-retry with JS)

## 📊 Current Configuration

- **Products per search**: 5
- **Timeout**: 120 seconds
- **Max cost per request**: 10 credits
- **Min description length**: 50 chars
- **Max description length**: 2000 chars
- **Auto-retry with JS**: Enabled

## 🌐 Access Points

- **Frontend**: http://localhost:5000
- **API Search**: http://localhost:5000/api/search
- **API Extract**: http://localhost:5000/api/extract
- **API Batch**: http://localhost:5000/api/extract-batch

## 📝 Example Search Queries

Try these:
- "wireless headphones"
- "coffee maker"
- "gaming laptop"
- "smart watch"
- "range hood"
- "microwave oven"

## 💡 Tips

1. **Be specific**: "Sony wireless headphones" vs "headphones"
2. **Wait for completion**: Extraction takes 5-30 seconds per product
3. **Check confidence**: High confidence = more reliable data
4. **Export results**: Save JSON for later analysis
5. **Watch the neural network**: It reacts to your mouse!

## 🎯 What's Happening Behind the Scenes

1. **SERP API** searches Google Shopping for popular products
2. **Organic link enrichment** finds product detail pages
3. **ScraperAPI** fetches HTML (bypassing bot protection)
4. **NLP Extractor** uses semantic matching to find descriptions:
   - Checks JSON-LD structured data
   - Searches for semantic section headings
   - Uses multiple fallback methods
5. **Confidence scoring** rates extraction quality
6. **Results** are displayed with rich metadata

## 🚦 Status Indicators

### Loading Page
- **Spinning icon**: In progress
- **✓ Green**: Success
- **✗ Red**: Failed

### Results Page
- **Green badge**: High confidence (80%+)
- **Yellow badge**: Medium confidence (60-79%)
- **Red badge**: Low confidence (<60%)

## 📤 Export Format

Exported JSON structure:
```json
{
  "query": "wireless headphones",
  "timestamp": "2026-01-14T12:34:56.789Z",
  "products": [
    {
      "title": "Product Name",
      "url": "https://...",
      "meta_title": "...",
      "meta_description": "...",
      "product_description": "...",
      "extraction_method": "jsonld",
      "confidence_score": 0.95
    }
  ]
}
```

## 🛠️ For Developers

### Run in debug mode
```python
# app.py
app.run(debug=True, host='0.0.0.0', port=5000)
```

### Test API endpoints
```bash
# Search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"headphones"}'

# Extract
curl -X POST http://localhost:5000/api/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/product"}'
```

### View logs
Check the terminal where `python app.py` is running.

## 📚 Documentation

- [WEB_APP_README.md](WEB_APP_README.md) - Complete documentation
- [ENHANCED_EXTRACTOR_README.md](ENHANCED_EXTRACTOR_README.md) - Extractor details
- [STRANDBAGS_FIX_SUMMARY.md](STRANDBAGS_FIX_SUMMARY.md) - Bot protection fix

## ❤️ Enjoy!

You're now ready to extract product intelligence from the web with style!

---

**Need help?** Check the full documentation in [WEB_APP_README.md](WEB_APP_README.md)
