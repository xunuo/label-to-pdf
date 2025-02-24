import ollama

def summarize_text(text):
    prompt = (
        f"Please provide a concise, well-structured summary of the following article, ensuring factual accuracy"
        f" Provide only the summary without any additional text: {text}"
    )
    response = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]

def generate_title(summary):
    prompt = (
        f"Based on the summary provided, generate a catchy, creative, and engaging title, just the title nothing more "
        f"Provide only the title without any additional text or qutation: {summary}"
    )
    response = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]

def generate_description(summary):
    prompt = (
        f"Generate a list 3 concise descriptions for this summary. just the descriptions nothing more "
        f"Provide only the descriptions, seperated by newline only: {summary}"
    )
    response = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]
