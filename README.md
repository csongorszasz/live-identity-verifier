# live-identity-verifier

## Goal
Web-based GUI with real-time webcam streaming for automatic identity verification of the user by comparing
their face and their identity card photo, and validating the text content of the identity card.

## Architecture
Microservices, orchastrated with Docker Compose.

## Tech stack
- Backend: Python, WebRTC, OpenCV, dlib, EasyOCR
- Frontend: JavaScript, React, WebRTC

## Demo 

https://github.com/user-attachments/assets/4d3a5760-f16b-43f0-835c-c99d99caee83

## Setup

1. Run in terminal: `docker compose up -d`
2. Access web GUI at: `http://localhost:80`
