# Geo-Regulation Governance MVP

A quick MVP for the "From Guesswork to Governance" hackathon prompt. This project provides a simple, maintainable FastAPI backend that uses simulated LLM workflows to extract compliance criteria from legal texts and verify documents against them.

## Key Features

-   **Simple & Maintainable**: All backend logic is contained within a single `app` folder.
-   **Dockerized**: Easily run the entire stack (FastAPI + MongoDB) with one command.
-   **Modern Tech Stack**: Built with FastAPI for high performance and Pydantic for robust data validation.
-   **Simulated LLM Workflows**: Mimics the behavior of two Dify workflows for criteria extraction and document verification.


## Getting Started

### Prerequisites

-   Docker and Docker Compose must be installed on your machine.

### Running the Application

1.  **Clone the repository and checkout the active_changes branch**
2.  **Navigate to the project directory.**
3.  **Create the .env**

    The .env template is as follows:
    
    ```
    # Your Dify API base URL (e.g., https://api.dify.ai/v1)
    DIFY_BASE_URL=
    # MongoDB Configuration
    MONGO_URI=

    DIFY_EXTRACT_API_KEY=
    DIFY_VERIFY_API_KEY=
    DIFY_KB_API_KEY=
    DIFY_DATASET_ID=
    DIFY_DATASET_API_KEY=

    VITE_API_BASE=

    MONGO_INITDB_ROOT_USERNAME=
    MONGO_INITDB_ROOT_PASSWORD=
    MONGO_URI=
    ```

    For the Organising Committe, please email us for the Environment File to run the application.

4.  **Launch the services using Docker Compose:**

    ```bash
    docker-compose up --build
    ```

    This command will build the FastAPI container and pull the MongoDB image, then start both services. The API will be available at `http://localhost:8000`.

### Using the application

1. In the browser of your preferance, go to `http://localhost:5173/`
2. Click on `Admin Ingestion` in the Navigation Bar 
    - This simulates an authenticated admin uploading the legal documents to be refered to
3. Click on `Compliance Check` in the Navigation Bar
4. Select the legal document to check for compliance against
5. Upload/Choose a `Project Document` which you need to check the compliance of
6. Pick the requirements you want to check if the uploaded `Project Document` fufils 
7. Click `Run Verification` and see the results

## How It Works

### Model pipeline

To allow the LLM to parse the information, we implemented a Retrieval Augmented Generation framework with 2 inputs.
We used Dify to streamline the deployment process.

**Inputs**
1. Legal Document
2. Project Document

**Model Workflow**
1. Ingestion of Legal Document 

    The legal document is fed into the LLM, which chunks the document into the respectives laws that projects have to abide by, according to the prompt given to the LLM.
    It also extracts fields like: 
    - Summary
    - Actionable Verbs, eg. Store
    - Target of action, eg. Personal data
    - Conditions that the law holds, eg. During data processing activities
    - Keywords, eg. "data minimisation", "storage limitation"
    - Exceptions, eg. Public interest archiving
    These chunks are then returned to the Backend, which stores it in a database, along with other peripheral metadata, like the name and region of the legal document.

2. Ingestion of Project Doucment

    The project document is then uploaded and sent for indexing.

3. Verfication of Project Document

    For each criteria selected by the user, the Dify workflow concatenates the prompt, the document, the criteria and other relevant data (eg. the name and region of the legal document), and queries the LLM.
    The LLM then generates a templated JSON response with: 
    1. Compliance status
    2. Confidence score
    3. Reasoning
    4. Supporting Evidence from the Project Document that the LLM referenced
    5. Whether to flag for human review


### Backend
The main backend logic is implemented as two main API endpoints:

1.  **`POST /extract-criteria/`**:
    -   **Input**: A legal document (name, citation, text).
    -   **Process**: This endpoint simulates the first Dify prompt (`prompt1`) to parse the legal text and extract structured, actionable compliance criteria.
    -   **Output**: The extracted criteria are returned and saved to the MongoDB database for future use.

2.  **`POST /verify-document/`**:
    -   **Input**: A feature document (e.g., PRD, TRD) and a specific `criterion_id` to check against.
    -   **Process**: This simulates the second Dify prompt (`prompt2`) by comparing the document text against the stored legal criterion.
    -   **Output**: A JSON object detailing whether the document is `COMPLIANT`, `NON_COMPLIANT`, or `AMBIGUOUS_NEEDS_REVIEW`, along with supporting evidence.

**Access the Interactive API Docs:**

    Open your browser and go to `http://localhost:8000/docs` to see the auto-generated Swagger UI documentation. You can test the endpoints directly from this interface.


## Development Tools & Libraries

-   **Backend**: Python 3.9, FastAPI
-   **Database**: MongoDB
-   **Containerization**: Docker, Docker Compose
-   **Libraries**: Uvicorn, Pydantic, PyMongo