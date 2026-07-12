from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    app_name: str
    app_env: str
    auth_mode: str
    database: str
