# JetFriend v2.0 - Your Intelligent AI Travel Companion

JetFriend is an advanced travel planning application that combines the power of OpenAI's GPT-4o with real-time location data from Google Places API to provide personalized, detailed travel recommendations.

## ✨ Features

### 🤖 AI-Powered Travel Assistant
- **GPT-4o Integration**: Advanced conversational AI with specialized travel expertise
- **JetFriend Personality**: Enthusiastic, knowledgeable travel expert persona
- **Itinerary Planning**: Day-by-day travel plans with specific recommendations
- **Budget Tips**: Money-saving strategies and discount recommendations
- **Clickable Links**: Direct links to Google Maps and travel resources

### 📍 Real-Time Location Intelligence
- **Google Places Integration**: Live restaurant, hotel, and attraction data
- **Smart Query Detection**: Automatically identifies when location data is needed
- **Local Recommendations**: Real places with ratings, addresses, and map links
- **Context-Aware Responses**: AI incorporates real venue data into recommendations

### 🚀 Enhanced API Endpoints
- `/api/chat` - Enhanced chat with automatic location data integration
- `/api/places` - Direct location search endpoint
- `/api/health` - System status with API connectivity checks
- `/api/test-ai` - OpenAI GPT-4o connectivity testing
- `/api/test-places` - Google Places API connectivity testing

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.11+
- OpenAI API Key (GPT-4o access)
- Google Places API Key

### Installation

1. **Clone and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env with your actual API keys
   OPENAI_API_KEY=your-openai-api-key-here
   GOOGLE_PLACES_API_KEY=your-google-places-api-key-here
   ```

3. **Run the application:**
   ```bash
   python3 app.py
   ```

4. **Access the application:**
   - Main App: `http://localhost:5000`
   - Health Check: `http://localhost:5000/api/health`

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o access |
| `GOOGLE_PLACES_API_KEY` | Yes | Google Places API key for location data |
| `DEBUG` | No | Set to `true` for debug mode (default: false) |
| `PORT` | No | Custom port number (default: 5000) |

## 📡 API Documentation

### Chat Endpoint
```http
POST /api/chat
Content-Type: application/json

{
  "message": "Find me good restaurants in Paris",
  "history": [...]  // Optional conversation history
}
```

**Response:**
```json
{
  "success": true,
  "response": "Here are some amazing restaurants in Paris...",
  "places_found": 3,
  "enhanced_with_location": true,
  "timestamp": "2024-..."
}
```

### Places Search Endpoint
```http
POST /api/places
Content-Type: application/json

{
  "query": "coffee shops",
  "location": "New York",
  "radius": 5000  // Optional, in meters
}
```

**Response:**
```json
{
  "success": true,
  "places": [
    {
      "name": "Blue Bottle Coffee",
      "address": "123 Main St, New York, NY",
      "rating": 4.5,
      "url": "https://maps.google.com/maps/place/?q=place_id:..."
    }
  ],
  "count": 5
}
```

## 🧠 JetFriend AI Personality

JetFriend is designed as an expert travel companion with:

- **Enthusiastic & Knowledgeable**: Acts like a well-traveled friend who's excited to help
- **Practical Focus**: Provides actionable advice with specific recommendations
- **Budget-Conscious**: Always includes money-saving tips and alternatives
- **Local Expertise**: Suggests authentic experiences beyond tourist traps
- **Itinerary Style**: Structures responses with clear day-by-day plans
- **Link-Rich**: Provides clickable links to maps, venues, and resources

## 🎯 Smart Features

### Automatic Location Detection
JetFriend automatically detects when your query needs real-time location data:

✅ **Triggers location search:**
- "Best restaurants in Tokyo"
- "Hotels near Times Square"
- "Coffee shops around me"
- "Things to do in Paris"

### Enhanced AI Responses
When location data is found, JetFriend:
1. Fetches real places from Google Places API
2. Incorporates venue details into the AI prompt
3. Provides responses with actual place names, ratings, and links
4. Maintains conversational flow while being factually accurate

### Premium Feature Messaging
For unavailable features, JetFriend naturally mentions upgrading to premium:
- "Upgrade to JetFriend Premium for real-time availability and exclusive deals!"

## 🚦 System Status

Check API connectivity:
- **Health**: `GET /api/health`
- **OpenAI Status**: `GET /api/test-ai`
- **Google Places Status**: `GET /api/test-places`

## 🔐 Security Notes

- API keys are never logged or exposed in responses
- Environment variables are used for all sensitive configuration
- Placeholder keys are safely handled without causing crashes

## 📝 Development

### Local Development
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables in `.env`
3. Run: `python3 app.py`
4. The app auto-reloads on file changes in debug mode

### Testing
```bash
# Test health endpoint
curl http://localhost:5000/api/health

# Test AI connectivity
curl http://localhost:5000/api/test-ai

# Test Places API
curl http://localhost:5000/api/test-places
```

## 📄 License

MIT License - Created by Steven Gobran, Steven Alfy, Anton Salib

---

**Ready to explore the world with your AI travel companion!** 🌍✈️
