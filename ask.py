"""Ask a question on the command line and return a result to the command line from ollama."""
#Author: Dana McNeil

import json
import os
import sys
import urllib.request
import urllib.error
import subprocess
import argparse

OLLAMA_URL = "https://ollama.com/api/generate"
DEFAULT_MODEL = "gemma4:cloud"

#get the args from the command line

    
def get_model_name():
    model = os.environ.get("OLLAMA_MODEL")
    if model is None or model == "":
        model = DEFAULT_MODEL
    return model

def get_api_key():
    key = os.environ.get("OLLAMA_API_KEY")
    if key is None or key == "":
        print("Ollama API key has not been set.  Check ~/.bashrc for the configuration.", file=sys.stderr)
        sys.exit(1)
    return key

def build_request(question, model):
    payload = {
        "model": model,
        "prompt": question,
        "system": "You are an assistant to an Arch Linux user.  The user may ask questions on any topic but often about Linux commands.  Return as brief a response/answer as possible.",
        "stream": True,
    }
    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + get_api_key(),
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers=headers,
        method="POST",
    )
    return request

def copy_text(text):
    """Copy text to the Wayland clipboard using wl-copy."""
    try:
        subprocess.run(["wl-copy"], input=text, text=True, check=True)
    except FileNotFoundError:
        print("Could not copy: wl-copy is not installed.", file=sys.stderr)
    except subprocess.CalledProcessError:
        print("Could not copy: wl-copy failed.", file=sys.stderr)

def ask(question, copy_to_clipboard):
    model = get_model_name()
    request = build_request(question, model)
    answer_parts = []

    try:
        with urllib.request.urlopen(request) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if line == "":
                    continue

                chunk = json.loads(line)

                text = chunk.get("response", "")
                print(text, end="", flush=True)
                answer_parts.append(text)

                if chunk.get("done") is True:
                    break

    except urllib.error.HTTPError as error:
        # The server answered, but with an error code (401, 404, 429, ...).
        if error.code == 401:
            print("Error 401: API key was rejected. Check OLLAMA_API_KEY.", file=sys.stderr)
        elif error.code == 404:
            print(f"Error 404: model '{model}' not found. Check the list from /api/tags.", file=sys.stderr)
        elif error.code == 429:
            print("Error 429: rate limit reached. Wait a bit and try again.", file=sys.stderr)
        elif error.code == 500:
            print("Error 500: the ollama server had a problem.Try again later.", file=sys.stderr)
        else:
            print(f"HTTP error {error.code}: {error.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        # We never got a response: no network, DNS failure, etc.
        print(f"Could not reach {OLLAMA_URL}: {error.reason}", file=sys.stderr)
        return 1

    print()  # final newline after the streamed answer
    if copy_to_clipboard:
        answer = "".join(answer_parts)
        copy_text(answer)
    return 0

def writeContext(context):
    #write the context to the temp folder for this user.
    #the temp folder should be named based on this shell's process id, so that multiple shells can have different contexts.
    shell_pid = os.getppid()
    #Check if this folder already exists, if not create it.
    tempFile = os.path.join("/tmp", f"ollama_context_{shell_pid}")
    if tempFile is None or tempFile == "":
        print("Could not determine shell temp folder.", file=sys.stderr)
        exit(1)
    #create the folder if it doesn't exist
    if not os.path.exists(tempFile):
        os.makedirs(tempFile)
   #write the context to a file in this folder
    open(os.path.join(tempFile, "context.txt"), "w").write(context)
    

def main():
    parser = argparse.ArgumentParser(description="Ask a question to the Ollama API.")
    parser.Add_argument("-c", "--copy", action="store_true", help="Copy the answer to the clipboard")
    parser.Add_arguement("-s","--set_context", type=str, help="Set the context for the question")

    args = parser.parse_args()

    if args.set_context is not None:
        #write the context to a file in the user's home directory
        writeContext(args.set_context)

    copy_to_clipboard = False
    if len(args) > 0 and args[0] == "-c":
        copy_to_clipboard = True
        args = args[1:]
    if len(args) == 0:
        print("Usage: ?? [-c], <your question>", file=sys.stderr)
        return 1

    question = " ".join(args)
    return ask(question, copy_to_clipboard)

if __name__ == "__main__":
    sys.exit(main())
