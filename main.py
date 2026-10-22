# uv run --env-file .env python main.py
import os

API_KEY: str | None = os.getenv(key="API_KEY")  # Load from .env file

def main():
    print("Hello from translationtools!")

print(API_KEY)
if __name__ == "__main__":
    main()
