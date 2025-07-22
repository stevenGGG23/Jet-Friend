# JetFriend - Your AI Travel Companion

JetFriend is an intelligent travel companion powered by AI that helps users plan trips, find destinations, book flights, discover local attractions, and provide travel advice.

## 🚀 Features

- **AI-Powered Chat**: Intelligent travel assistance using OpenRouter API
- **Modern UI**: Beautiful, responsive interface with dark theme
- **Real-time Chat**: Seamless conversation experience with typing indicators
- **Travel-Focused**: Specialized AI assistant trained for travel-related queries
- **Mobile-Ready**: Optimized for both desktop and mobile devices

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.11+
- OpenRouter API key (for AI functionality)

### Installation Steps

1. **Clone the repository** (if using git):
   ```bash
   git clone <repository-url>
   cd jetfriend
   ```

2. **Install Python dependencies**:
   ```bash
   python3 -m pip install --break-system-packages Flask Flask-CORS openai python-dotenv
   ```
   
   Or use the npm script:
   ```bash
   npm run install-deps
   ```

3. **Configure environment variables**:
   - Copy `.env.example` to `.env`
   - Get an API key from [OpenRouter.ai](https://openrouter.ai/)
   - Add your OpenRouter API key to the `.env` file:
   ```bash
   OPENROUTER_API_KEY=your_actual_api_key_here
   PORT=5000
   DEBUG=True
   ```

   **Note**: The app will still work without an API key, but AI responses will be limited to a configuration message.

4. **Start the development server**:
   ```bash
   npm run dev
   # or
   python3 app.py
   ```

5. **Open your browser** and visit `http://localhost:5000`

## 🔧 API Endpoints

The Flask backend provides the following REST API endpoints:

- `GET /` - Serves the main application
- `GET /api/health` - Health check endpoint
- `GET /api/test` - Test AI connectivity
- `POST /api/chat` - Send chat messages to AI

### Chat API Example

```javascript
// Send a message to JetFriend
fetch('/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: "Plan a 3-day trip to Paris",
    history: [] // Optional conversation history
  })
})
.then(response => response.json())
.then(data => console.log(data.response));
```

## 🔑 Getting an OpenRouter API Key

1. Visit [OpenRouter.ai](https://openrouter.ai)
2. Sign up for an account
3. Navigate to your API keys section
4. Create a new API key
5. Copy the key to your `.env` file

## 🏗️ Architecture

- **Frontend**: Vanilla HTML/CSS/JavaScript with modern responsive design
- **Backend**: Flask REST API with CORS support
- **AI Integration**: OpenRouter API (Microsoft MAI DS R1 model)
- **Styling**: Custom CSS with gradient themes and animations

## 📝 Development

### Running with Debug Mode

The application runs in debug mode by default in development. To change this:

```bash
# In .env file
DEBUG=False
```

### API Testing

Test the API endpoints using curl:

```bash
# Health check
curl http://localhost:5000/api/health

# Test AI connectivity
curl http://localhost:5000/api/test

# Send a chat message
curl -X POST -H "Content-Type: application/json" \
  -d '{"message": "Hello JetFriend!"}' \
  http://localhost:5000/api/chat
```

## 🚨 Troubleshooting

### Common Issues

1. **"OPENROUTER_API_KEY not configured"**
   - Make sure you've set the API key in your `.env` file
   - Restart the server after adding the key

2. **Port already in use**
   - Change the PORT in your `.env` file
   - Or stop any other services using port 5000

3. **Import errors**
   - Make sure all dependencies are installed
   - Try reinstalling with the --break-system-packages flag

### Without API Key

The application will still work without an OpenRouter API key, but AI responses will be limited to a message indicating the key needs to be configured.

## 📱 Features Showcase

- **Intelligent Chat Interface**: Real-time conversation with travel-focused AI
- **Beautiful UI**: Modern glassmorphism design with smooth animations
- **Mobile Responsive**: Optimized for all screen sizes
- **Error Handling**: Graceful error handling with user-friendly messages
- **Loading States**: Visual feedback for better user experience

## 🌟 Future Enhancements

- User authentication and conversation history
- Integration with travel booking APIs
- Offline functionality
- Push notifications
- Multi-language support
- Voice input/output capabilities

## 📄 License

MIT License - see LICENSE file for details.

## 👥 Authors

- Steven Gobran
- Steven Alfy  
- Anton Salib

---

Built with ❤️ for travelers everywhere.
