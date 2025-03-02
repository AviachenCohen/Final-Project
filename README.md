# Exceptional Package Management System

## Overview

This repository contains the backend API for the Exceptional Package Management System. The project was developed to
automate the tracking and management of exceptional packages within a logistics chain. It streamlines operations by
monitoring package statuses, generating alerts for overdue updates, and providing real-time data analysis to support
informed decision-making.

## Features

- **Robust API**: Built with Flask, offering endpoints for package retrieval, status updates, and report generation.
- **Data Management**: Utilizes MongoDB (via PyMongo) for efficient storage and querying of package data.
- **Automation**: Employs APScheduler to schedule tasks that check for overdue packages and trigger email notifications.
- **Asynchronous Processing**: Integrates Celery and Redis to handle batch updates (e.g., processing CSV uploads)
  without interrupting real-time operations.
- **Real-Time Reporting**: Supports the generation of analytical reports to monitor logistics performance.

## Architecture & Tech Stack

- **Backend Framework**: Flask (Python)
- **Database**: MongoDB
- **Task Scheduling & Asynchronous Processing**: APScheduler, Celery, Redis
- **Email Integration**: SMTP (using smtplib)
- **Deployment**: Configured for cloud deployment (e.g., Heroku)

## Installation & Setup

1. **Clone the Repository**:

   ``git clone https://github.com/yourusername/exceptional-package-management.git``

   ``cd exceptional-package-management``
2. **Create a Virtual Environment & Install Dependencies**:

   ``python -m venv .venv``

   ``source .venv/bin/activate  # Windows: .venv\Scripts\activate``

   ``pip install -r requirements.txt``

3. **Configure Environment Variables**:
    - Create a .env file based on the provided .env.example (which lists all required variables with placeholder
      values).
    - Note: Ensure the actual .env file is excluded from version control via .gitignore.
4. **Run the Application**:

   ``flask run``

5. **Run the Celery Worker (if required)**:

   ``celery -A app.celery worker --loglevel=info``


## Documentation & Presentation

#### For a detailed overview of the project’s design, implementation, and outcomes:

  - [Final Project Presentation](final%20project%20presentation.pdf)


## Notes

- The Wix-based front-end is a private system and is not included in this repository.
- This repository is provided for demonstration purposes only.









