import httpx

r = httpx.post("http://localhost:8000/auth/login", json={
    "username": "new_user123@example.com",
    "password": "password123"
})
print(r.status_code, r.text)
