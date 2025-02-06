import ollama

def ask(question: str, return_response: bool = False):
    # Asking the model and allow the model generate a response using the model
    response = ollama.generate(model='deepseek-r1:7b', prompt=question)
    print(response['response'])
    if return_response:
        return response['response']
    return None

if __name__ == '__main__':
    your_question = input("Type a what you want to ask: ")
    ask(question=your_question, return_response=False)

