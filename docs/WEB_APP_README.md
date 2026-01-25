# Fluxer Atelier - Web Application

A beautiful, interactive web application for intelligent product discovery and extraction.

## Features

### **Page 1: Query Input**
- Clean, luxury-themed interface
- Single text input for product search queries
- Examples: "wireless headphones", "coffee maker", "gaming laptop"
- GO button to start the discovery process

### **Page 2: Loading Progress**
- Real-time loading indicators with animations
- Shows progress for:
  1. **Searching for popular products** (SERP API)
  2. **Fetching product URLs** (organic links)
  3. **Extracting descriptions** (ScraperAPI + NLP)
- Success/failure indicators for each step
- Error messages if something goes wrong

### **Page 3: Results Display**
- Beautiful product cards showing:
  - **Product Title** (from SERP)
  - **Meta Title** (from webpage)
  - **Meta Description** (from webpage)
  - **Product Description** (extracted with NLP)
  - **Confidence Score** (High/Medium/Low badge)
  - **Extraction Method** (jsonld, semantic_section, etc.)
  - **Source Link** (view original page)
- Export results as JSON
- "New Search" button to start over

## Architecture

```
Frontend (HTML/CSS/JS)
    ↓
Flask Backend (app.py)
    ↓
    ├─→ serp_pipeline.py (SERP API)
    │   └─→ get_popular_products.py
    │
    └─→ html_product_extractor.py (NLP Extraction)
        └─→ ScraperAPI integration
```

## API Endpoints

### `POST /api/search`
Search for popular products using SERP API.

**Request:**
```json
{
  "query": "wireless headphones"
}
```

**Response:**
```json
{
  "status": "success",
  "query": "wireless headphones",
  "products": [
    {
      "title": "Sony WH-1000XM4",
      "price": "$349.99",
      "source": "Amazon",
      "link": "https://..."
    }
  ],
  "count": 5
}
```

### `POST /api/extract`
Extract product description from a single URL.

**Request:**
```json
{
  "url": "https://example.com/product"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "url": "https://...",
    "meta_title": "Product Title",
    "meta_description": "Short description",
    "product_description": "Full extracted description",
    "extraction_method": "jsonld",
    "confidence_score": 0.95
  }
}
```

### `POST /api/extract-batch`
Extract descriptions for multiple products at once.

**Request:**
```json
{
  "products": [
    {
      "title": "Product 1",
      "link": "https://..."
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "results": [
    {
      "title": "Product 1",
      "url": "https://...",
      "meta_title": "...",
      "product_description": "...",
      "extraction_method": "semantic_section",
      "confidence_score": 0.85
    }
  ],
  "total": 5,
  "successful": 4
}
```

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**

   Create a `.env` file:
   ```bash
   SERP_API_KEY=your_serp_api_key_here
   SCRAPER_API_KEY=your_scraper_api_key_here
   ```

3. **Run the Flask app:**
   ```bash
   python app.py
   ```

4. **Open in browser:**
   ```
   http://localhost:5000
   ```

## Usage

### Step 1: Enter Query
1. Open the app in your browser
2. Type a product search query (e.g., "wireless headphones")
3. Click "Start Discovery"

### Step 2: Watch Progress
- The app will show real-time progress:
  - ✓ Searching for popular products...
  - ✓ Extracting: Sony WH-1000XM4...
  - ✓ Extracting: Bose QuietComfort 45...
  - etc.

### Step 3: View Results
- Browse extracted product information
- See confidence scores and extraction methods
- Click "View Source" to visit original pages
- Export results as JSON for further analysis
- Click "New Search" to start over

## Features Highlights

### 🎨 Beautiful UI
- Luxury-themed design with gold accents
- Animated neural network background
- Smooth page transitions
- Responsive design for mobile/tablet/desktop

### 🚀 Real-time Progress
- Live loading indicators
- Success/error states for each product
- Clear error messages if something fails

### 🧠 Intelligent Extraction
- Advanced NLP-based extraction
- Multiple extraction methods (JSON-LD, semantic, etc.)
- Confidence scoring for each extraction
- Automatic retry with JavaScript rendering for blocked sites

### 📊 Rich Results
- Product titles, meta data, and full descriptions
- Confidence badges (High/Medium/Low)
- Extraction method tags
- Direct links to source pages

### 💾 Export Capability
- Export all results as JSON
- Includes query, timestamp, and all product data
- Easy to integrate with other tools

## Configuration

### Extraction Settings

Edit `app.py` to adjust extraction settings:

```python
html_extractor = HTMLProductExtractor(
    timeout_s=120,        # Request timeout
    max_cost="10",        # ScraperAPI cost limit
    min_chars=50,         # Minimum description length
    max_chars=2000,       # Maximum description length
    debug=False,          # Debug mode
    auto_retry_with_js=True  # Auto-retry with JS
)
```

### SERP Settings

Adjust in the `/api/search` endpoint:

```python
aggregated = SerpProcessor.fetch_products(
    [query],
    limit=5,           # Number of products to fetch
    device='desktop',  # 'desktop' or 'mobile'
    api_key=None       # Uses SERP_API_KEY from env
)
```

## Troubleshooting

### Issue: "SERP_API_KEY not found"
**Solution**: Set `SERP_API_KEY` in your `.env` file.

### Issue: "SCRAPER_API_KEY not found"
**Solution**: Set `SCRAPER_API_KEY` in your `.env` file.

### Issue: Products found but descriptions not extracted
**Possible causes**:
- Bot protection on target websites
- Invalid URLs
- ScraperAPI quota exceeded

**Solutions**:
1. Check ScraperAPI dashboard for errors
2. Increase `max_cost` in settings
3. Enable `render_js` for JavaScript-heavy sites

### Issue: Slow extraction
**Causes**:
- JavaScript rendering is slow (takes 5-10 seconds per URL)
- Multiple products being processed sequentially

**Solutions**:
- Use fewer products (adjust `limit` parameter)
- Be patient - quality extraction takes time

### Issue: Low confidence scores
**Causes**:
- Unusual page structure
- Limited content on page
- Meta fallback used

**Solutions**:
- Check the extraction method (prefer 'jsonld' or 'semantic_section')
- View source page to verify content exists
- Adjust `min_chars` if descriptions are legitimately short

## Development

### File Structure
```
GenericProductFluxer/
├── app.py                          # Flask backend
├── templates/
│   └── index.html                  # Frontend UI
├── html_product_extractor.py      # NLP extraction
├── serp_pipeline.py                # SERP integration
├── serp_services/
│   └── get_popular_products.py     # SERP logic
├── .env                            # API keys (not in git)
├── requirements.txt                # Python dependencies
└── WEB_APP_README.md               # This file
```

### Adding New Features

**To add a new API endpoint:**
1. Add route in `app.py`:
   ```python
   @app.route('/api/my-endpoint', methods=['POST'])
   def my_endpoint():
       # Your logic here
       return jsonify({'status': 'success'})
   ```

2. Call from frontend:
   ```javascript
   const response = await fetch('/api/my-endpoint', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({ data: 'value' })
   });
   ```

**To modify the UI:**
1. Edit `templates/index.html`
2. CSS is in `<style>` tag
3. JavaScript is in `<script>` tag at bottom

### Debug Mode

Enable debug mode to see detailed logs:

```python
# In app.py
html_extractor = HTMLProductExtractor(
    debug=True  # Enable debug output
)
```

Run Flask in debug mode:
```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

## API Costs

### SERP API
- ~1 credit per search query
- ~1 credit per organic link enrichment
- **Total per query: ~6 credits** (1 search + 5 product links)

### ScraperAPI
- 1 credit per standard request
- 5 credits per JavaScript rendering request
- **Total per product: 1-6 credits** (1 standard, up to 6 if retry with JS)

### Example Cost Calculation
For 1 search with 5 products:
- SERP API: ~6 credits
- ScraperAPI: ~5-30 credits (depending on bot protection)
- **Total: ~11-36 credits per query**

## Production Deployment

### Option 1: Local Deployment
```bash
python app.py
# Access at http://localhost:5000
```

### Option 2: Gunicorn (Linux/Mac)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Option 3: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

### Environment Variables for Production
```bash
SERP_API_KEY=your_key
SCRAPER_API_KEY=your_key
FLASK_ENV=production
SECRET_KEY=your_secret_key
```

## Security Considerations

1. **API Keys**: Never commit `.env` to git
2. **Rate Limiting**: Add rate limiting for production:
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app, default_limits=["100 per hour"])
   ```
3. **CORS**: Restrict origins in production:
   ```python
   CORS(app, origins=['https://yourdomain.com'])
   ```
4. **Input Validation**: Validate user inputs
5. **Error Handling**: Don't expose internal errors to users

## Support

For issues or questions:
1. Check this README
2. Review [STRANDBAGS_FIX_SUMMARY.md](STRANDBAGS_FIX_SUMMARY.md) for extraction issues
3. Review [ENHANCED_EXTRACTOR_README.md](ENHANCED_EXTRACTOR_README.md) for extractor details
4. Check API provider dashboards for quota/errors

## License

Private project - All rights reserved.

---

**Built with ❤️ using Flask, BeautifulSoup, and Advanced NLP**
