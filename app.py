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

# Initialize OpenRouter API
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    logger.warning("OPENROUTER_API_KEY not set. AI functionality will be limited.")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_ai_response(user_message, conversation_history=None):
    """
    Send a message to OpenRouter and get a response
    """
    if not api_key:
        return "I'm sorry, but AI functionality is currently unavailable. Please set the OPENROUTER_API_KEY environment variable to enable AI responses."

    try:
        # Build messages array for OpenRouter
        messages = [
            {
                "role": "system",
                "content": "You are JetFriend, an intelligent AI travel companion. Follow these guidelines:\n\nPERSONALITY & TONE:\n- Be friendly, enthusiastic, and knowledgeable about travel\n- Use a conversational, helpful tone\n- Be concise but thorough\n- Show excitement about travel and destinations\n\nFORMATTING RULES:\n- Keep responses under 200 words when possible\n- Use simple formatting that works in chat\n- For lists, use \"•\" bullet points or numbered items (1., 2., 3.)\n- Use line breaks for better readability\n- Avoid complex markdown or special characters\n\nTRAVEL EXPERTISE:\n- Focus on practical, actionable travel advice\n- Ask clarifying questions about budget, dates, preferences\n- Suggest specific destinations, activities, and tips\n- Consider seasonality, weather, and local events\n- Mention approximate costs when relevant\n\nRESPONSE STRUCTURE:\n- Start with enthusiasm/acknowledgment\n- Ask 1-2 key questions if needed\n- Provide specific recommendations\n- End with an engaging follow-up question"
            }
        ]

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        # Prepare the request payload for OpenRouter
        payload = {
            "model": "microsoft/phi-3-medium-128k-instruct:free",
            "messages": messages
        }

        # Make the API request
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'X-Title': 'JetFriend',
            'HTTP-Referer': 'https://jetfriend.com'
        }

        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)

        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                return content.strip()
            else:
                return "I'm sorry, I didn't receive a proper response. Please try again."
        else:
            logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
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
            'error': 'OPENROUTER_API_KEY not configured',
            'ai_status': 'disconnected',
            'message': 'Please set the OPENROUTER_API_KEY environment variable to enable AI functionality.'
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
