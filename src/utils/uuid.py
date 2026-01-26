import requests

def format_uuid(u):
    u = u.replace("-", "").strip()
    return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}"
