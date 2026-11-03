"""Ask a question on the command line and return a result to the command line from ollama."""
#Author: Dana McNeil

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

#CONSTANTS
OLLAMA_URL = "https://ollama.com/api/generate" #<--  Path to the ollama API endpoint for generating responses.
DEFAULT_MODEL = "gemma4:cloud" #<-- Default model to use if OLLAMA_MODEL is not set in the environment variable.
CONTEXT_FILE = os.path.join("/tmp","ai_commandline/context", f"{os.getppid()}.tmp") #<-- Path to the context file in the temp folder.
    
def get_model_name():
    """Return the name of the model defined in the environement varaible."""
    model = os.environ.get("OLLAMA_MODEL")
    if model is None or model == "":
        model = DEFAULT_MODEL
    return model

def get_api_key():
    """Returns the API key which is stored in the environment variable OLLAMA_API_KEY.  If it is not set, print an error message and exit."""
    key = os.environ.get("OLLAMA_API_KEY")
    if key is None or key == "":
        print("Ollama API key has not been set.  Check ~/.bashrc for the configuration.", file=sys.stderr)
        sys.exit(1)
    return key

def loadContext():
    #load the context from the file in the temp folder for this user process if it exists.
    if not os.path.exists(CONTEXT_FILE):
        return ""
    
    with open(CONTEXT_FILE, "r") as f:
        return f.read()

def build_request(question, model, args):
    """Returns the formatted request for the Ollama API."""
    #get the command arguments.
    
    systemPrompt = "You are an assistant to an Arch Linux user.  The user may ask questions on any topic but often about Linux commands.  Return as brief a response/answer as possible. Your response is output to the command line so so not output any complex formatting markdown. "
    context = loadContext()
    if len(context) > 0:
        systemPrompt += f"  With regard to {context}: "
    if args.debug :
        print(systemPrompt + "\n")
    
    payload = {
        "model": model,
        "prompt": question,
        "system": systemPrompt,
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

def ask(question, argParser):
    """Send a question to the Ollama API and print the answer to stdout."""

    model = get_model_name()
    request = build_request(question, model,argParser)
    answer_parts = []

    try:
        theContext = loadContext()
        if theContext != "":
            print(f"[context: {theContext}]")
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
    return 0

def writeContext(context):
    #write the context to the temp folder for this user.
    #the temp folder should be named based on this shell's process id, so that multiple shells can have different contexts.
    
    #create the file if it doesn't exist
    if not os.path.exists(CONTEXT_FILE):
        os.makedirs(os.path.dirname(CONTEXT_FILE), exist_ok=True)
   #write the context to a file in this folder
    with open(CONTEXT_FILE, "w") as f:
        f.write(context)
    

def main():
    parser = argparse.ArgumentParser(description="Ask a question to the Ollama API.")
    parser.add_argument("-c", "--copy", action="store_true", help="Copy the answer to the clipboard")
    parser.add_argument("-s","--set_context", type=str, help="Set the context for the question")
    parser.add_argument("question", nargs="*", type=str, help="The question to ask")
    parser.add_argument("-d", "--debug",action="store_true", help="Flag to enable debugging output." )
    parser.add_argument("--clear-context", action="store_true", help="Clear the context for the question")
    
    args = parser.parse_args()

    if args.set_context is not None:
        #write the context to a file in the user's home directory
        writeContext(args.set_context)
    elif args.clear_context:
        #Just write an empty string to the context file to clear it. An empty string is treated as no context set.
        writeContext("")

    if len(args.question) == 0:
        print("Usage: ask.py [-h] [-c] [-s SET_CONTEXT] question", file=sys.stderr)
        return 1
    question = " ".join(args.question)
    if len(question) > 0:
        return ask(question,args)

if __name__ == "__main__":
    sys.exit(main())
