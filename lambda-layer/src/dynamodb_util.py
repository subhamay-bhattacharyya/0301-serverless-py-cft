"""Module providing a library of utility functions related to AWS DynamoDB with logging and tracing support."""

from __future__ import annotations
from typing import Any, Optional
import logging

from botocore.exceptions import ClientError
from botocore.client import BaseClient as Client
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

# Initialize a module-level logger
logger = logging.getLogger(__name__)


def handle_client_error(func):
    def wrapper(*args, **kwargs):

        """
        A decorator function that wraps another function to provide logging and optional tracing.

        Args:
            *args: Positional arguments to be passed to the wrapped function.
            **kwargs: Keyword arguments to be passed to the wrapped function. It can include:
                - logger (logging.Logger): A logger instance to log errors. Defaults to a global logger.
                - tracer: An optional tracer instance to create tracing spans and capture exceptions.

        Returns:
            The result of the wrapped function.

        Raises:
            ClientError: If an error occurs while interacting with DynamoDB, it logs the error and re-raises the exception.
        """

        log: logging.Logger = kwargs.get("logger", logger)
        tracer = kwargs.get("tracer", None)  # Extract tracer if provided

        try:
            if tracer:
                with tracer.start_span(name=func.__name__):  # Optional tracing span
                    return func(*args, **kwargs)
            return func(*args, **kwargs)

        except ClientError as e:
            error_message = (
                f"DynamoDB Error in {func.__name__}: {e.response['Error']['Message']}"
            )
            log.error(error_message)

            if tracer:
                tracer.capture_exception(e)  # Capture error in tracing system

            raise e

    return wrapper


@handle_client_error
def deserialize_item(
    item: dict[str, Any], tracer: Optional[Any] = None
) -> dict[str, Any]:
    """
    Deserializes a DynamoDB item from its attribute value format to a standard Python dictionary.

    Args:
        item (dict[str, Any]): The DynamoDB item to be deserialized.
        tracer (Optional[Any], optional): An optional tracer for tracing the deserialization process. Defaults to None.

    Returns:
        dict[str, Any]: The deserialized item as a standard Python dictionary.
    """

    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in item.items()}


@handle_client_error
def serialize_item(
    item: dict[str, Any], tracer: Optional[Any] = None
) -> dict[str, Any]:
    """
    Serializes a given dictionary item using DynamoDB's TypeSerializer.

    Args:
        item (dict[str, Any]): The dictionary item to be serialized.
        tracer (Optional[Any], optional): An optional tracer object for tracing. Defaults to None.

    Returns:
        dict[str, Any]: The serialized dictionary item.
    """

    serializer = TypeSerializer()
    return {k: serializer.serialize(v) for k, v in item.items()}


@handle_client_error
def get_item(
    dynamodb_client: Client,
    table_name: str,
    key: dict[str, Any],
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> dict[str, Any]:

    """
    Fetches an item from a DynamoDB table.

    This function retrieves an item from a DynamoDB table using the provided key.
    It handles client errors and optionally logs the operation and captures tracing events.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for the operation.
        table_name (str): The name of the DynamoDB table to fetch the item from.
        key (dict[str, Any]): The key of the item to fetch from the DynamoDB table.
        logger (Optional[logging.Logger], optional): The logger to use for logging the operation. Defaults to None.
        tracer (Optional[Any], optional): The tracer to use for capturing tracing events. Defaults to None.

    Returns:
        dict[str, Any]: The retrieved item from the DynamoDB table, deserialized if present, otherwise an empty dictionary.
    """

    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event(f"Fetching DynamoDB item: {key}")

    response = dynamodb_client.get_item(TableName=table_name, Key=key)
    return deserialize_item(response["Item"], tracer) if "Item" in response else {}


@handle_client_error
def put_item(
    dynamodb_client: Client,
    table_name: str,
    item: dict[str, Any],
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> dict[str, Any]:

    """
    Puts an item into a DynamoDB table.

    This function serializes the given item and puts it into the DynamoDB table using the provided DynamoDB client.
    It also logs the operation and optionally traces it if a tracer is provided.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for the operation.
        table_name (str): The name of the DynamoDB table to put the item into.
        item (dict[str, Any]): The item to put into the DynamoDB table.
        logger (Optional[logging.Logger]): The logger to use for logging the operation. If not provided, a default logger is used.
        tracer (Optional[Any]): The tracer to use for tracing the operation. If not provided, tracing is skipped.

    Returns:
        dict[str, Any]: The response from the DynamoDB client after putting the item.

    Raises:
        botocore.exceptions.ClientError: If there is an error during the put operation.
    """

    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event(f"Putting DynamoDB item: {item}")

    serialized_item = serialize_item(item, tracer)
    return dynamodb_client.put_item(TableName=table_name, Item=serialized_item)


@handle_client_error
def batch_write_item(
    dynamodb_client: Client,
    table_name: str,
    items: list[dict[str, Any]],
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> None:

    """
    Puts multiple items into a DynamoDB table using batch writer.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for the operation.
        dynamodb_table (str): The name of the DynamoDB table to put the items into.
        items (list[dict[str, Any]]): A list of items to put into the DynamoDB table.
        logger (Optional[logging.Logger], optional): Logger for logging information. Defaults to None.
        tracer (Optional[Any], optional): Tracer for capturing events. Defaults to None.

    Returns:
        None

    Raises:
        botocore.exceptions.ClientError: If there is an error with the DynamoDB client operation.
    """

    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event(f"Updating DynamoDB item: {items}")

    return dynamodb_client.batch_write_item(
        RequestItems={
            table_name: [
                {
                    "PutRequest": {
                        "Item": serialize_item(item, tracer),
                    }
                }
                for item in items
            ]
        }
    )


@handle_client_error
def update_item(
    dynamodb_client: Client,
    table_name: str,
    key: dict[str, Any],
    update_expression: str,
    expression_attribute_names: dict[str, Any],
    expression_attribute_values: dict[str, Any],
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> dict[str, Any]:

    """
    Updates an item in a DynamoDB table.

    This function uses the provided DynamoDB client to update an item in the table
    based on the given key, update expression, and expression attribute values.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for the update operation.
        table_name (str): The name of the DynamoDB table to update the item in.
        key (dict[str, Any]): The primary key of the item to be updated.
        update_expression (str): An update expression specifying the attributes to be updated.
        expression_attribute_names (dict[str, Any]): A dictionary of attribute names to be used in the update expression.
        expression_attribute_values (dict[str, Any]): A dictionary of values to be used in the update expression.
        logger (Optional[logging.Logger], optional): A logger instance for logging. Defaults to None.
        tracer (Optional[Any], optional): A tracer instance for capturing events. Defaults to None.

    Returns:
        dict[str, Any]: The response from the DynamoDB update_item operation.

    Raises:
        botocore.exceptions.ClientError: If the update operation fails.
    """

    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event(f"Updating DynamoDB item: {key}")

    response = dynamodb_client.update_item(
        TableName=table_name,
        Key=key,
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="ALL_NEW",
    )
    response.update({"updatedItem": deserialize_item(response["Attributes"], tracer)})

    return response


@handle_client_error
def delete_item(
    dynamodb_client: Client,
    table_name: str,
    key: dict[str, Any],
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> dict[str, Any]:

    """
    Deletes an item from a DynamoDB table.

    This function deletes an item from a DynamoDB table using the provided key.
    It also logs the deletion process and optionally captures a tracing event.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for the operation.
        table_name (str): The name of the DynamoDB table to delete the item from.
        key (dict[str, Any]): The key of the item to delete.
        logger (Optional[logging.Logger], optional): The logger to use for logging. Defaults to None.
        tracer (Optional[Any], optional): The tracer to use for capturing events. Defaults to None.

    Returns:
        dict[str, Any]: The response from the DynamoDB delete_item operation.

    Raises:
        botocore.exceptions.ClientError: If there is an error during the delete operation.
    """

    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event(f"Deleting DynamoDB item: {key}")

    response = dynamodb_client.delete_item(
        TableName=table_name, Key=key, ReturnValues="ALL_OLD"
    )
    response.update({"deletedItem": deserialize_item(response["Attributes"], tracer)})
    return response


@handle_client_error
def query_items(
    dynamodb_client: Client,
    table_name: str,
    key_condition_expression: str,
    expression_attribute_names: dict[str, Any],
    expression_attribute_values: dict[str, Any],
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> list[dict[str, Any]]:

    """
    Queries items from a DynamoDB table using the provided key condition expression and attribute values.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for querying.
        table_name (str): The name of the DynamoDB table to query.
        key_condition_expression (str): The key condition expression for the query.
        expression_attribute_names (dict[str, Any]): The attribute names used in the key condition expression.
        expression_attribute_values (dict[str, Any]): The values for the expression attributes.
        logger (Optional[logging.Logger], optional): Logger for logging information. Defaults to None.
        tracer (Optional[Any], optional): Tracer for capturing events. Defaults to None.

    Returns:
        list[dict[str, Any]]: A list of items returned by the query.
    """
    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event("Executing DynamoDB query")

    response = dynamodb_client.query(
        TableName=table_name,
        KeyConditionExpression=key_condition_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
    )
    response.update(
        {"items": [deserialize_item(item) for item in response.get("Items", [])]}
    )
    return response


@handle_client_error
def scan_items(
    dynamodb_client: Client,
    table_name: str,
    filter_expression: str,
    expression_attribute_names: dict[str, Any],
    expression_attribute_values: dict[str, Any],
    projection_expression: str,
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """
    Scans items from a DynamoDB table using a filter expression.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for the scan operation.
        table_name (str): The name of the DynamoDB table to scan.
        filter_expression (str): The filter expression to apply to the scan.
        expression_attribute_names (dict[str, Any]): The attribute names used in the filter expression.
        expression_attribute_values (dict[str, Any]): The values to use in the filter expression.
        projection_expression (str): The projection expression to apply to the scan.
        logger (Optional[logging.Logger], optional): Logger instance for logging. Defaults to None.
        tracer (Optional[Any], optional): Tracer instance for capturing events. Defaults to None.

    Returns:
        list[dict[str, Any]]: A list of items returned by the scan operation.
    """

    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event("Executing DynamoDB scan")

    response = dynamodb_client.scan(
        TableName=table_name,
        FilterExpression=filter_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
        ProjectionExpression=projection_expression,
    )
    response.update(
        {"items": [deserialize_item(item) for item in response.get("Items", [])]}
    )
    return response


@handle_client_error
def query_all_items(
    dynamodb_client: Client,
    table_name: str,
    key_condition_expression: str,
    expression_attribute_names: dict[str, Any],
    expression_attribute_values: dict[str, Any],
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """
    Queries all items from a DynamoDB table using the provided key condition expression
    and attribute values.

    Args:
        dynamodb_client (Client): The DynamoDB client to use for querying.
        table_name (str): The name of the DynamoDB table to
        key_condition_expression (str): The key condition expression for the query.
        expression_attribute_names (dict[str, Any]): The attribute names used in the key
        condition expression.
        expression_attribute_values (dict[str, Any]): The values for the expression attributes.
        logger (Optional[logging.Logger], optional): Logger for logging information.
        Defaults to None.
        tracer (Optional[Any], optional): Tracer for capturing events. Defaults to None.

    Returns:
        list[dict[str, Any]]: A list of items returned by the query.
    """
    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event("Executing DynamoDB query")

    response = dynamodb_client.query(
        TableName=table_name,
        KeyConditionExpression=key_condition_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
    )
    return [deserialize_item(x, tracer) for x in response.get("Items", [])]


@handle_client_error
def get_item_count(
    dynamodb_client: Client,
    table_name: str,
    logger: Optional[logging.Logger] = None,
    tracer: Optional[Any] = None,
) -> Any:
    """
    Retrieves the count of items in a DynamoDB table.

    Args:
        dynamodb_client (Client): The boto3 DynamoDB client.
        table_name (str): The name of the DynamoDB table.
        logger (Optional[logging.Logger]): Logger instance for logging. If not provided, a default
            logger will be used.
        tracer (Optional[Any]): Tracer instance for capturing events. If provided, an event for
            counting items will be captured.

    Returns:
        int: The count of items in the DynamoDB table.
    """
    logger = logger or logging.getLogger(__name__)
    if tracer:
        tracer.capture_event("Counting DynamoDB items")

    response = dynamodb_client.describe_table(TableName=table_name)
    return response
