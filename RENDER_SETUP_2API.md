# JetFriend Setup Guide for Render (2-API Version)

## ✅ Simplified Configuration - Only 2 APIs Needed!

Your JetFriend app now works with just **2 API keys** instead of 4:

1. **OPENAI_API_KEY** - For AI chat responses (ChatGPT)
2. **GOOGLE_PLACES_API_KEY** - For location data AND images

## 🚀 Render Deployment Setup

### Step 1: Environment Variables in Render

In your Render dashboard, go to your service and add these **Environment Variables**:

```
OPENAI_API_KEY = sk-your-actual-openai-api-key-here
GOOGLE_PLACES_API_KEY = your-actual-google-places-api-key-here
```

### Step 2: Deploy Commands

Set these in your Render service:

- **Build Command**: `echo "No build needed"`
- **Start Command**: `python3 simple_server_2api.py`

## 🔑 Getting Your API Keys

### OpenAI API Key (for ChatGPT)
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up/login and go to API Keys
3. Create a new secret key
4. Copy it to `OPENAI_API_KEY` in Render

### Google Places API Key (for locations + images)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable these APIs:
   - **Places API** 
   - **Places API (New)**
4. Create credentials → API Key
5. Copy it to `GOOGLE_PLACES_API_KEY` in Render

## ✨ What You Get

With just these 2 APIs, your app will have:

- ✅ **AI Chat** - Smart travel responses via ChatGPT
- ✅ **Location Search** - Find restaurants, hotels, attractions
- ✅ **Real Images** - Photos from Google Places Photo API
- ✅ **Maps Integration** - Direct Google Maps links
- ✅ **Place Details** - Ratings, reviews, addresses
- ✅ **Website Links** - Official websites when available

## 🔧 Testing Your Setup

After deploying to Render:

1. Visit your app URL
2. Click the "Test API" button in the chat interface
3. You should see: "OpenAI: connected" and "Google Places: connected"
4. Try asking: "Best restaurants in Paris"
5. You should see place cards with real images from Google!

## 💰 Cost Optimization

- **OpenAI**: Uses `gpt-3.5-turbo` (most cost-effective)
- **Google Places**: Only charges for actual searches (not per image)
- No additional image API costs!

## 🆘 Troubleshooting

### If Chat Doesn't Work:
- Check `OPENAI_API_KEY` is correct
- Ensure you have credits in your OpenAI account

### If No Images/Places Show:
- Check `GOOGLE_PLACES_API_KEY` is correct
- Ensure Places API is enabled in Google Cloud
- Check you have billing enabled (Google requires it even for free tier)

### If Port Issues:
- The app auto-detects available ports (5001, 5002, etc.)
- Check Render logs for the actual port being used

## 📱 Features That Work

- ✅ Restaurant recommendations with photos
- ✅ Hotel suggestions with ratings
- ✅ Tourist attractions with real images
- ✅ Interactive place cards
- ✅ Google Maps integration
- ✅ Responsive design
- ✅ Real-time chat

Perfect for travel planning with minimal API complexity! 🎉
