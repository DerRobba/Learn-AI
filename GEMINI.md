# Project Overview

This project is a Python-based web application called "Learn-AI", designed as an AI-powered learning assistant. It's built using the Flask framework and interacts with a SQLite database to manage its data.

The core functionalities of the application include:

*   **User Authentication:**  The application supports three user roles: `student`, `teacher`, and `it-admin`. Each role has different permissions and views within the application.
*   **Chat Interface:** A real-time chat interface allows users to interact with an AI model. The application stores the chat history for each user.
*   **Assignment Management:** Teachers can create, view, and delete assignments. Students can view assignments and submit their work.
*   **Text-to-Speech:** The application uses the ElevenLabs API to convert text to speech.
*   **PDF Generation:** The application can generate PDF worksheets from Markdown content.

## Building and Running

To run this project, you need to have Python and the required packages installed.

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set up Environment Variables:**
    Create a `.env` file in the root directory of the project and add the following variables:

    ```
    SECRET_KEY=your-secret-key
    BASE_URL=your-openai-compatible-base-url
    MODEL=your-model-name
    API_KEY=your-api-key
    ELEVENLABS_API_KEY=your-elevenlabs-api-key
    ELEVENLABS_VOICE_ID=your-elevenlabs-voice-id
    SYSTEM_PROMPT="Your system prompt for the AI model"
    VISION_SYSTEM_PROMPT="Your system prompt for the vision model"
    IP_BAN_LIST=
    ```

3.  **Run the Application:**
    ```bash
    python app.py
    ```
    The application will be available at `http://127.0.0.1:5000`.

## Development Conventions

*   **Database:** The application uses a SQLite database (`users.db`) to store all its data. The `database.py` file contains all the necessary functions to interact with the database.
*   **Styling:** The project uses `context_menu.css` for styling the context menu.
*   **Frontend Logic:** The main frontend logic is in `main.js`.
*   **Templates:** The HTML templates are located in the `templates` directory.
*   **File Storage:**
    *   `sheets`: Stores generated `.md` and `.pdf` files.
    *   `uploads`: Stores uploaded `.mp3` files.
