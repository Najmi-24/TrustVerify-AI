import os
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None

def answer_document_question(question, document):
    document_text = document.get("text", "") or document.get("summary", "")

    if not document_text:
        return "I cannot answer because no document content is available."

    prompt = f"""
You are TrustVerify AI, a smart document assistant.

Answer the user's question in a natural, human-like way.

Rules:
- If the answer is in the document, use it.
- If not, give a helpful explanation related to the document.
- Do NOT mention "from document" or "general knowledge".
- Keep the answer clear, short, and helpful.
- Explain like you are talking to a normal user.

DOCUMENT SUMMARY:
{document.get("summary", "")}

DOCUMENT CONTENT:
{document_text}

DOCUMENT VERDICT:
{document.get("verdict", "")}

USER QUESTION:
{question}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        return response.choices[0].message.content

    except Exception as e:
        print("GROQ ERROR:", e)
        return "AI failed. Please try again."