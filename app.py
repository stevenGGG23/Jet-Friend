from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Initialize Google Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.warning("GEMINI_API_KEY not set. AI functionality will be limited.")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

def get_ai_response(user_message, conversation_history=None):
    """
    Send a message to Google Gemini and get a response
    """
    if not api_key:
        return "I'm sorry, but AI functionality is currently unavailable. Please set the GEMINI_API_KEY environment variable to enable AI responses."

    try:
        # Create the prompt with system context and conversation history
        full_prompt = """You are JetFriend, an intelligent AI travel companion. Follow these guidelines:

PERSONALITY & TONE:
- Be friendly, enthusiastic, and knowledgeable about travel
- Use a conversational, helpful tone
- Be concise but thorough
- Show excitement about travel and destinations

FORMATTING RULES:
- Keep responses under 200 words when possible
- Use simple formatting that works in chat
- For lists, use "•" bullet points or numbered items (1., 2., 3.)
- Use line breaks for better readability
- Avoid complex markdown or special characters

TRAVEL EXPERTISE:
- Focus on practical, actionable travel advice
- Ask clarifying questions about budget, dates, preferences
- Suggest specific destinations, activities, and tips
- Consider seasonality, weather, and local events
- Mention approximate costs when relevant

RESPONSE STRUCTURE:
- Start with enthusiasm/acknowledgment
- Ask 1-2 key questions if needed
- Provide specific recommendations
- End with an engaging follow-up question

EXAMPLES OF GOOD RESPONSES:
"Exciting! Paris in spring is magical!

To help plan your perfect trip:
• What's your budget range?
• How many days will you stay?
• Interested in museums, food, or nightlife?

I can suggest the best neighborhoods to stay in and must-see spots based on your preferences!"

"""

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                role = "Human" if msg.get("role") == "user" else "Assistant"
                full_prompt += f"{role}: {msg.get('content', '')}\n"

        # Add current user message
        full_prompt += f"Human: {user_message}\nAssistant:"

        # Prepare the request payload for Gemini
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": full_prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048
            }
        }

        # Make the API request
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(f"{GEMINI_API_URL}?key={api_key}", headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            if 'candidates' in data and len(data['candidates']) > 0:
                content = data['candidates'][0]['content']['parts'][0]['text']
                return content.strip()
            else:
                return "I'm sorry, I didn't receive a proper response. Please try again."
        else:
            logger.error(f"Gemini API error: {response.status_code} - {response.text}")
            return f"I'm sorry, I'm having trouble connecting right now. Please try again in a moment. Error: {response.status_code}"

    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        return f"I'm sorry, I'm having trouble connecting right now. Please try again in a moment. Error: {str(e)}"

@app.route('/')
def serve_index():
    """Serve the main HTML file"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get AI response
        ai_response = get_ai_response(user_message, conversation_history)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'timestamp': request.timestamp if hasattr(request, 'timestamp') else None
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'Sorry, I encountered an error processing your request.'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'JetFriend API',
        'version': '1.0.0'
    })

@app.route('/api/test', methods=['GET'])
def test_ai():
    """Test AI connectivity"""
    if not api_key:
        return jsonify({
            'success': False,
            'error': 'GEMINI_API_KEY not configured',
            'ai_status': 'disconnected',
            'message': 'Please set the GEMINI_API_KEY environment variable to enable AI functionality.'
        }), 503

    try:
        test_response = get_ai_response("Hello! Can you tell me you're working correctly?")
        return jsonify({
            'success': True,
            'test_response': test_response,
            'ai_status': 'connected'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'ai_status': 'disconnected'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

    print(f"🚀 JetFriend API starting on port {port}")
    print(f"🌐 Visit: http://localhost:{port}")

    app.run(host='0.0.0.0', port=port, debug=debug_mode)
