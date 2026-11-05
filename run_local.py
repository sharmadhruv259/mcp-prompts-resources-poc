"""Run the FastAPI backend locally using the Neon testing database."""

import os

import uvicorn
from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def main() -> None:
    """Start the development server with the testing database.

    Args:
        None.

    Returns:
        None: Runs the FastAPI development server.

    Raises:
        ValueError: If database URLs are missing or share the same host.
    """
    values = dotenv_values(".env")

    production = values.get("DATABASE_URL")
    testing = values.get("TEST_DATABASE_URL")

    if not production or not testing:
        raise ValueError("Missing production or testing database URL.")

    if make_url(production).host == make_url(testing).host:
        raise ValueError("Production and testing hosts must differ.")

    os.environ["DATABASE_URL"] = testing

    print("Starting FastAPI with Neon testing database...", flush=True)

    uvicorn.run(
        "api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()