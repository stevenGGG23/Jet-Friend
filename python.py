import os
from openai import OpenAI

# Initialize the OpenAI client with OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),  # Securely stored API key
)

def get_ai_response(user_message):
    """
    Send a message to Microsoft MAI DS R1 and get a response
    """
    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://stevenggg23.github.io/Jet-Friend/",
                "X-Title": "Jet Friend",
            },
            model="microsoft/mai-ds-r1:free",
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# Example usage
if __name__ == "__main__":
    response = get_ai_response("Hello! Tell me about yourself.")
    print(response)
