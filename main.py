# uv run --env-file .env python script.py
import os
deepl_free_key = os.getenv(key="DEEPLFREEKEY")  # Load from .env file

def main():
    print("Hello from translationtools!")

print(deepl_free_key)
if __name__ == "__main__":
    main()
