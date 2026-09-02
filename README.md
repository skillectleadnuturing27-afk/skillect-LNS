# FastAPI Lead Management API

A REST API built using FastAPI and PostgreSQL for managing leads.

This project supports CRUD operations, search, filtering, pagination, and duplicate email validation.
## Features

- Create a new lead
- Get all leads
- Get a single lead by ID
- Update lead details
- Delete a lead
- Search leads by name and email
- Filter leads by status and source
- Pagination support
- Duplicate email validation
- 404 error handling
- Swagger API documentation
## Tech Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- Uvicorn
- Postman
- Git & GitHub
## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /leads | Create a new lead |
| GET | /leads | Get all leads |
| GET | /leads/{lead_id} | Get a single lead |
| PUT | /leads/{lead_id} | Update a lead |
| DELETE | /leads/{lead_id} | Delete a lead |
## Search, Filter and Pagination

### Filter by Status
GET /leads?status=new

### Filter by Source
GET /leads?source=Instagram

### Search by Name
GET /leads?name=Irfan

### Search by Email
GET /leads?email=gmail.com

### Pagination
GET /leads?skip=0&limit=5

### Combined Filter
GET /leads?status=new&source=Instagram
## How to Run the Project

1. Clone the repository

   git clone https://github.com/skillectleadnuturing27-afk/skillect.git

2. Open the project folder

   cd skillect

3. Install required packages

   pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv

4. Create a `.env` file and configure PostgreSQL database credentials.

5. Start the FastAPI server

   uvicorn main:app --reload

6. Open Swagger API documentation

   http://127.0.0.1:8000/docs

## API Documentation

After starting the server, Swagger UI is available at:

http://127.0.0.1:8000/docs

## Project Status

Backend MVP completed with CRUD operations, validation, filtering, search and pagination.
