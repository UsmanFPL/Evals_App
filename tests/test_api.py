import pytest
from fastapi import status

@pytest.mark.asyncio
async def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_unauthorized_access(client):
    response = client.get("/api/v1/projects")
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,  # If auth is enabled
        status.HTTP_404_NOT_FOUND     # If endpoints are not implemented yet
    ]

@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
