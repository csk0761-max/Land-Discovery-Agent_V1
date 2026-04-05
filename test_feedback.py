import requests

data = {
    "context": "When evaluating flat land for solar",
    "correction": "Always prioritize land with slope < 5%"
}

try:
    response = requests.post("http://localhost:8000/feedback", json=data)
    print("Status Code:", response.status_code)
    print("Response Base:", response.json())
except Exception as e:
    print("Error:", e)
