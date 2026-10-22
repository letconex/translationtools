# uv run --env-file .env python main.py
import os

API_KEY: str | None = os.getenv(key="API_KEY")  # Load from .env file
print(API_KEY)

def main():
    print("Hello from translationtools!")

if __name__ == "__main__":
    main()
