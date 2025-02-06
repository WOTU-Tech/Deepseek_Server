import subprocess


def ollama_deepseek_command(query: str = "Who are you?"):
    command = "ls -l"  # List files in the current directory

    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print("Command Output:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error occurred:", e)