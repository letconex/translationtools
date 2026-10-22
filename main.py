# uv run --env-file .env python script.py
import os
key = os.getenv(key="DEEPLFREEKEY")  # Load from .env file

def main():
    print("Hello from translationtools!")

print(key)
if __name__ == "__main__":
    main()
