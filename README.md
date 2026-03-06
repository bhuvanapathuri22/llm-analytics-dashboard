# LLM-Powered Analytics Dashboard

This project is an AI-powered analytics dashboard that allows users to query manufacturing or business data using natural language. The system interprets user questions using a Large Language Model (LLM) and converts them into structured data operations to generate insights and visualizations.

The application is built using Streamlit, Pandas, Plotly, and Gemini API to create an interactive data analytics interface.

---

## Features

- Natural language query interface
- LLM-based query understanding
- Data analysis using Pandas
- Interactive visualizations using Plotly
- Streamlit dashboard interface
- Automatic metric detection and aggregation

---

## System Architecture

User Query  
↓  
Streamlit Interface  
↓  
Query Understanding Engine (LLM + Rule-Based NLP)  
↓  
Data Processing (Pandas)  
↓  
Aggregation & Metrics Calculation  
↓  
Visualization (Plotly Charts)  
↓  
Dashboard Output

---

## Technologies Used

- Python
- Streamlit
- Pandas
- Plotly
- Google Gemini API (LLM)
- SQLite Database

---

## Project Structure


llm-analytics-dashboard
│
├── app.py
├── manufacturing.db
├── requirements.txt
└── README.md


---

## Installation

Clone the repository


## git clone https://github.com/your-username/llm-analytics-dashboard.git


Navigate to project folder


## cd llm-analytics-dashboard


Install dependencies


## pip install -r requirements.txt


Run the application


## streamlit run app.py


---

## Example Queries

- Total revenue for the last 3 months  
- Top 5 products by sales  
- Bottom 3 customers by revenue  
- Monthly sales trend  
- Revenue by region  

---

## Author

**Pathuri Bhuvaneswari**
