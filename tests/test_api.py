from fastapi import status

def test_read_main(client):
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

def test_unauthorized_access(client):
    response = client.get("/api/v1/projects")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
