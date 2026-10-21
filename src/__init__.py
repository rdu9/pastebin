from fastapi import FastAPI

version = "v1"

app = FastAPI(
    version=version,
    title="Pastebin",
    description = "Pastebin app, using k8s."
)