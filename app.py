import streamlit as st
import pandas as pd
from datetime import datetime
import holidays
import json
import requests


# Validate the sum of percentages for activities
def validate_percentages(tickets_data):
    for ticket_id, pct_total, pct_dist in tickets_data:
        if sum(pct_dist.values()) != 100:
            return False
    return True


# Function to calculate working days
def working_days(start_date, end_date):
    se_holidays = holidays.Sweden()  # Change to your country's holidays
    return len(
        [
            d
            for d in pd.date_range(start_date, end_date)
            if d.weekday() < 5 and d not in se_holidays
        ]
    )


# Streamlit app layout
st.title("Work Hours Distribution App")

# User inputs
start_date, end_date = st.columns(2)
with start_date:
    start_date = st.date_input("Start Date", datetime(2023, 11, 15))
with end_date:
    end_date = st.date_input("End Date", datetime(2023, 12, 14))

total_hours = st.number_input("Total Hours", value=176)
account_id = st.text_input(
    "Enter your Tempo Account ID", "712020:8d686d57-0a6c-4793-b194-0e20e8ade696"
)
api_token = st.text_input("Enter your Tempo API token", "")


# Dynamic input fields based on the number of tickets
num_tickets = st.number_input("Number of EPIC TICKET IDs", 1, 10, 1)
tickets_data = []
for i in range(num_tickets):
    with st.expander(f"Ticket {i+1}"):
        ticket_id = st.text_input(f"EPIC TICKET ID {i+1}", f"SA-{355+i}")
        pct_total = st.slider(f"Percentage of Total for {ticket_id}", 0, 100, 50)
        pct_dist = {
            "ANALYSIS": 0,
            "DEV": 0,
            "BUGFIX": 0,
            "MEET": 0,
            "PM": 0,
            "SUPPORT": 0,
        }
        for act in pct_dist.keys():
            pct_dist[act] = st.slider(f"{act} for {ticket_id}", 0, 100, 0)
        tickets_data.append((ticket_id, pct_total, pct_dist))

# Calculate hours distribution
json_data = {}
if st.button("Calculate Distribution"):
    if validate_percentages(tickets_data):
        num_days = working_days(start_date, end_date)
        st.info(f"Number of working days: {num_days}", icon="ℹ")
        avg_hours_per_day = total_hours / num_days
        if avg_hours_per_day != 8:
            st.warning(
                f"Average working hours per day is {avg_hours_per_day}, which is not equal to 8."
            )
        for single_date in pd.date_range(start_date, end_date):
            if (
                single_date.weekday() < 5 and single_date not in holidays.Sweden()
            ):  # Adjust for your holidays
                date_str = single_date.strftime("%Y-%m-%d")
                json_data[date_str] = {}
                for ticket in tickets_data:
                    ticket_id, pct_total, pct_dist = ticket
                    ticket_hours = total_hours * (pct_total / 100)
                    daily_hours = ticket_hours / num_days
                    json_data[date_str][ticket_id] = {}
                    for act, pct in pct_dist.items():
                        act_hours = daily_hours * (pct / 100)
                        json_data[date_str][ticket_id][act] = act_hours
        # Write JSON data to file
        with open("payload.json", "w") as outfile:
            json.dump(json_data, outfile, indent=4)
    else:
        st.error("The sum of percentages for each activity must equal 100%")


# Send data to Tempo
def send_to_tempo(data, api_token):
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    for date, tickets in data.items():
        for ticket_id, activities in tickets.items():
            for activity, hours in activities.items():
                if hours > 0:
                    response = log_hours(
                        ticket_id,
                        datetime.strptime(date, "%Y-%m-%d"),
                        hours,
                        headers,
                        activity,
                    )
                    if response.status_code == 200:
                        st.success(
                            f"Logged {hours} hours of {activity} for {ticket_id} on {date}"
                        )
                    else:
                        st.error(
                            f"Failed to log hours for {ticket_id} on {date}: {response.text}"
                        )


def log_hours(issue_key, date, hours, headers, activity):
    url = "https://api.tempo.io/core/3/worklogs/"
    data = {
        "issueKey": issue_key,
        "timeSpentSeconds": hours * 3600,
        "startDate": date.strftime("%Y-%m-%d"),
        "startTime": "09:00:00",
        "description": f"Worked on {issue_key}",
        "authorAccountId": account_id,
        "attributes": [{"key": "_Account_", "value": activity.upper()}],
    }
    return requests.post(url, headers=headers, json=data)


if st.button("Send Data to Tempo"):
    if not api_token:
        st.error("API token is required")
    else:
        with open("payload.json", "r") as file:
            data = json.load(file)
            send_to_tempo(data, api_token)
