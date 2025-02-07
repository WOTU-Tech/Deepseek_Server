

# `Deepseek_Server`

This repository provides a step-by-step guide to setting up the DeepSeek R1 server powered by Ollama. The server is designed to expose a user-friendly HTML endpoint for seamless interaction, making it easy to access and query AI models deployed on your local device. With its lightweight architecture and API design, you can enjoy the convenience and have fun exploring the capabilities of this leading model.

Please pardon the rudimentary web design. This repository is intended to serve as a template for the local deployment of the DeepSeek-R1 model and its integration with a web API. You are encouraged to modify and optimize it as needed.

![api_screenshot.png](static/files/api_screenshot.png)

## `Step One`
Install Ollama with one command:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## `Step Two`
Download the DeepSeek-R1 model to your local machine. Please refer to the model [specifications](https://ollama.com/library/deepseek-r1) to select the version that best suits your hardware configuration. For example, my desktop, equipped with an RTX Titan (20GB VRAM) and 64GB RAM, performs optimally with the 32b model.

```bash
ollama pull deepseek-r1:32b
```

## `Step Three`
Create a virtual environment for this python API, if you use conda you can run:

```
conda env create -f environment.yml
```

## `Step Four`
Open your terminal and cd into the root folder: /Deepseek_Server

Activate your virtual environment run:
```
python3 __main__.py
```
Note: please change the "model_id" in the utils/parameter.yml to the id of the model you downloaded.
## `Step Five`
Open your browser and type in "http://127.0.0.1:5000", and type in your question and submit.

Please note that the chatbot caches your previous conversations by default. To clear the cache and start a new conversation, simply type "###" and submit.
