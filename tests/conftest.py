import os

# Settings are instantiated while importing the FastAPI application in test modules.
os.environ.setdefault("TASKHUB_JWT_SECRET_KEY", "test-jwt-secret-key-with-at-least-32-characters")
