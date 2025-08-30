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

1.  **Clone the repository.**
2.  **Navigate to the project directory.**
3.  **Launch the services using Docker Compose:**

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

To implement 
We use Dify to streamline 


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