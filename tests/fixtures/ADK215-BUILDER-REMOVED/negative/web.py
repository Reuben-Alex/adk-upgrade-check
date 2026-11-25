import httpx
from google.adk.cli import fast_api


def list_apps(base_url: str):
  return httpx.get(f"{base_url}/list-apps")


BUILD_DIR = "/home/me/builder"
