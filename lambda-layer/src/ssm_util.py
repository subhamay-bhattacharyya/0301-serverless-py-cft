"""Module providing a library of utility functions related to AWS Systems Manager (SSM)."""

from __future__ import annotations
from typing import Any
import logging

import boto3
from botocore.exceptions import ClientError
from botocore.client import BaseClient as Client

# Initialize a module-level logger
logger = logging.getLogger(__name__)


def handle_client_error(func):
    def wrapper(*args, **kwargs):
        """
        Wrapper function to handle logging and error handling for AWS SSM operations.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments. Expected keys:
                - logger (logging.Logger, optional): Logger instance to use for logging errors.
                    Defaults to a global logger.
                - tracer (optional): Tracer instance for capturing exceptions, e.g.,
                    AWS X-Ray tracer.

        Returns:
            The result of the wrapped function call.

        Raises:
            ClientError: If an error occurs during the execution of the wrapped function, it logs the error and re-raises the exception.
        """
        log: logging.Logger = kwargs.get("logger", logger)
        tracer = kwargs.get("tracer", None)  # Optional tracing

        try:
            return func(*args, **kwargs)
        except ClientError as e:
            error_message = (
                f"SSM Error in {func.__name__}: {e.response['Error']['Message']}"
            )
            log.error(error_message)

            if tracer:
                tracer.capture_exception(e)  # Example of AWS X-Ray tracing (optional)

            raise e

    return wrapper


@handle_client_error
def get_ssm_parameter(
    ssm_client: Client,
    name: str,
    logger: logging.Logger | None = None,
    tracer: Any = None,
) -> str:
    """
    Retrieve a parameter value from AWS Systems Manager Parameter Store.

    Args:
        ssm_client (Client): A boto3 SSM client.
        name (str): The name of the parameter to retrieve.
        logger (logging.Logger, optional): Logger instance for custom logging.
        tracer (Any, optional): Tracing instance for distributed tracing (e.g., AWS X-Ray).

    Returns:
        str: The decrypted value of the parameter.

    Raises:
        botocore.exceptions.ClientError: If there is an error retrieving the parameter.
    """
    # Ensure logger is set correctly
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info(f"Fetching SSM parameter: {name}")

    response = ssm_client.get_parameter(Name=name, WithDecryption=True)
    return response["Parameter"]["Value"]
