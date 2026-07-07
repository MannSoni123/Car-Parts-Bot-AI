# AI Car Part Chat Bot - Comprehensive Project Overview

## 1. Project Description & Capabilities
The **AI Car Part Chat Bot** is an advanced, AI-driven WhatsApp chatbot designed to assist users in identifying, searching for, and purchasing car parts. It streamlines the automotive parts lookup process by accepting various forms of user inputs (text, voice, images, documents) and intelligently responding with accurate part information, stock availability, and advice.

### Key Capabilities:
- **Multimodal Input Handling**: Can process text queries, voice notes (transcribing and translating them), images (running OCR to extract VINs or part numbers), and documents (PDF/Excel files for bulk part searches).
- **Intelligent Intent Understanding**: Uses LLMs to figure out exactly what the user wants—whether they are asking for a specific part, reporting a car issue (e.g., "my engine is overheating"), or providing a VIN.
- **Dynamic Database & Catalog Search**: Automatically searches a local database for parts. If a part relies on a VIN, it decodes the VIN and can scrape external catalogs (e.g., Partsouq) to find compatibility.
- **Multilingual Support**: Supports queries in various languages (like English, Hindi, Gujarati, Tamil, etc.), translates them internally to English for processing, and answers the user back in their native language.
- **Sales Agent Persona**: Formats responses to sound like a helpful, conversational sales agent rather than a robotic system.

---

## 2. How AI is Integrated
The project heavily leverages modern Artificial Intelligence, specifically the OpenAI API ecosystem, to power its brain:

1. **Natural Language Understanding (NLU) & Super Intent (`gpt_service.py`)**:
   - Uses **GPT-4o (or similar GPT models)** as the core brain. When a user sends a message, it is passed through a "Super Intent" prompt.
   - The AI identifies the context (greeting, part request, car issue, VIN provided).
   - It extracts exact entities (Part Names, Part Numbers).
   - It formats the final output into a professional, native-language "Sales Agent" response.
2. **Vision & OCR (`gpt_service.py` & `vin_ocr.py`)**:
   - Uses **GPT-4o Vision** to read images (like a photo of a car part, a dashboard warning light, or a VIN sticker) and extract text, part numbers, or descriptions.
3. **Voice Processing (`whisper_service.py`)**:
   - Uses **Whisper (`gpt-4o-mini-transcribe`)** to transcribe WhatsApp audio notes into text.
   - Uses a sub-agent to detect the language and clean up the transcription.
4. **Translation & Clarification**:
   - Uses AI to detect ambiguity. For example, if a user asks for a "filter", the AI dynamically asks "Do you mean Oil Filter, Air Filter, or Cabin Filter?"

---

## 3. Technology Stack

### Backend (Python/Flask)
- **Framework**: Flask (Python).
- **Database**: PostgreSQL (managed via SQLAlchemy and Flask-Migrate).
- **Task Queue & Background Processing**: Redis + RQ (Redis Queue). Used to handle WhatsApp webhooks asynchronously without timeout issues.
- **AI / Integrations**: `openai` python SDK, `deep-translator`.
- **Media & Document Processing**: `pdfplumber`, `pandas`, `openpyxl`, `pytesseract` (alongside GPT Vision).
- **Web Scraping**: Custom scrapers (e.g., Partsouq XPath Scraper via `curl_cffi` / `lxml`).

### Frontend (React/Vite)
- **Framework**: React 19 built with Vite.
- **Styling**: TailwindCSS, `clsx`, `tailwind-merge`.
- **Routing**: React Router DOM (`react-router-dom`).
- **Data Visualization**: Recharts (for dashboard analytics).
- **Icons**: Lucide React.

---

## 4. Key Workflows & Functionality

### A. The User Messaging Workflow (WhatsApp to Bot)
1. **Message Reception (`webhook.py`)**: A user sends a message via WhatsApp. The Meta/WhatsApp webhook triggers `POST /webhook`. 
2. **Queueing (`tasks.py`)**: The webhook immediately pushes the raw payload to a Redis queue and returns `200 OK` to WhatsApp (preventing timeouts).
3. **Batching & Processing (`collect_and_process_batch`)**: The RQ worker waits briefly (e.g., 6 seconds) to group multiple rapid texts or images from the same user into a single logical request.
4. **Entity Extraction (`document_service.py`, `whisper_service.py`, etc.)**: 
   - If audio: Transcribed via Whisper.
   - If image: OCR via GPT Vision.
   - If document: Parsed via `pdfplumber` or `pandas`.
5. **Unified processing (`message_processor.py`)**: All extracted text is combined. The system checks the database for existing part numbers.
6. **AI Super Intent Engine (`gpt_service.py`)**: Unrecognized descriptions are sent to GPT. GPT decides the intent, standardizes part names, and drafts the response.
7. **Delivery (`whatsapp_sender.py`)**: The generated AI response is sent back to the user's WhatsApp.

### B. Admin Dashboard Workflow
1. **Authentication**: Admins log in via the React frontend. Role-based access dictates permission levels (`admin` vs `super_admin`).
2. **Analytics (`Dashboard.jsx`)**: Displays metrics like total messages processed, API response times, and AI accuracy.
3. **Prompt Management (`PromptManager.jsx`)**: Super Admins can dynamically edit the "Super Intent" prompts stored in the database directly from the UI, tweaking the bot's behavior without deploying new code.

---

## Summary
The **AI Car Part Chat Bot** is a production-grade multimodal assistant. It combines a robust Python/Redis background worker architecture with state-of-the-art LLMs (GPT-4 / Whisper) to solve a complex real-world problem: accurately identifying matching automotive parts from fuzzy, multilingual user inputs (voice, image, text) and delivering an exceptional, real-time conversational experience via WhatsApp.
