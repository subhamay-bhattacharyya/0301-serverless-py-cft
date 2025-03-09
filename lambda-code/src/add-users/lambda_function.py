""" Lambda function to be used in the Serverless Patterns Lab-01"""

from typing import Any, Dict, Iterable, List, Optional
import os
import uuid
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from faker import Faker
import boto3
from botocore.exceptions import ClientError, ParamValidationError
from ssm_util import get_ssm_parameter
from dynamodb_util import (
    put_item,
    batch_write_item,
    get_item,
    update_item,
    query_items,
    delete_item,
    scan_items,
    get_item_count,
)
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from log_formatter import CustomFormatter

logger = Logger(service="serverless-lab-01", sample_rate_value = 0.1, logger_formatter=CustomFormatter())
tracer = Tracer(service="serverless-lab-01")
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])
dynamodb_client = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"])
DYNAMODB_TABLE_NAME = get_ssm_parameter(
    ssm_client=ssm_client,
    name=f"/{os.environ['PROJECT_NAME']}/{os.environ['ENVIRONMENT']}/dynamodb-table-name",
    logger=logger,
    tracer=tracer,
)


def batch_list_dicts(items_list: list[dict[str, Any]], batch_size: int):
    """Splits a list of dictionaries into batches of a given size."""
    for i in range(0, len(items_list), batch_size):
        yield items_list[i : i + batch_size]


@logger.inject_lambda_context(log_event=True)
# @tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    AWS Lambda function handler
    """
    logger.set_correlation_id({"awsRequestId": context.aws_request_id})
    logger.info("Hello from add users lambda")

    fake = Faker()
    operation = event.get("operation", None)
    if operation is None:
        return {
            "statusCode": 400,
            "isBase64Encoded": False,
            "body": {
                "message": "Missing operation parameter",
            },
        }

    if operation not in [
        "putItem",
        "batchWriteItem",
        "getItem",
        "updateItem",
        "queryItems",
        "deleteItem",
        "scanItems",
        "itemCount",
    ]:
        return {
            "statusCode": 400,
            "isBase64Encoded": False,
            "body": {
                "message": "Invalid operation parameter",
            },
        }

    """
    Example of put_item
    ###################################################################
    """
    if operation == "putItem":
        user = {
            "_id": str(uuid.uuid4()),
            "Name": event.get("name"),
            "Address": event.get("address"),
            "Email": event.get("email"),
            "Phone": event.get("phone"),
        }
        response = put_item(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            item=user,
            logger=logger,
        )

        status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        message = "Item added successfully"
        if status_code != 200:
            status_code = 400
            message = "Failed to add item, see CloudWatch logs for details."

        return {
            "statusCode": status_code,
            "isBase64Encoded": False,
            "body": {
                "message": message,
            },
        }

    """
    Example of batch_write_item
    ###################################################################
    """
    if operation == "batchWriteItem":
        user_count = event.get("userCount", 0)
        users = []
        for _ in range(int(event["userCount"])):
            users.append(
                {
                    "_id": str(uuid.uuid4()),
                    "Name": fake.name(),
                    "Address": fake.address().replace("\n", "."),
                    "Email": fake.email(),
                    "Phone": fake.phone_number(),
                }
            )
        users_batches = list(batch_list_dicts(items_list=users, batch_size=25))

        users.clear()
        for users_batch in users_batches:
            response = batch_write_item(
                dynamodb_client=dynamodb_client,
                table_name=DYNAMODB_TABLE_NAME,
                items=users_batch,
                logger=logger,
            )
            status_code = response["ResponseMetadata"]["HTTPStatusCode"]
            if status_code != 200:
                status_code = 400
                break
            users.extend(users_batch)

        return {
            "statusCode": status_code,
            "isBase64Encoded": False,
            "body": {"userCount": user_count, "usersWritten": users},
        }

    """
    Example of get_item
    ###################################################################
    """
    if operation == "getItem":
        partition_key = event.get("id")
        response = get_item(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            key={
                "_id": {
                    "S": partition_key,
                }
            },
            logger=logger,
        )
        status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if status_code != 200:
            status_code = 400
        return {
            "statusCode": status_code,
            "isBase64Encoded": False,
            "body": {
                "item": response or "No matching item found",
            },
        }

    """
    Example of update_item
    ###################################################################
    """
    if operation == "updateItem":
        partition_key = event.get("id")
        name = event.get("name", "NA")
        response = get_item(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            key={
                "_id": {
                    "S": partition_key,
                }
            },
            logger=logger,
        )

        if not response:
            return {
                "statusCode": 400,
                "isBase64Encoded": False,
                "body": {
                    "message": "No matching item found",
                },
            }
        response = update_item(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            key={
                "_id": {
                    "S": partition_key,
                }
            },
            update_expression="SET #Name = :Name",
            expression_attribute_names={
                "#Name": "Name",
            },
            expression_attribute_values={
                ":Name": {
                    "S": name,
                }
            },
            logger=logger,
        )
        status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        message = "Item updated successfully"
        if status_code != 200:
            status_code = 400
            message = "Failed to update item, see CloudWatch logs for details."

        return {
            "statusCode": status_code,
            "isBase64Encoded": False,
            "body": {"message": message, "updatedItem": response["updatedItem"]},
        }

    """"
    Example of query_items
    ###################################################################
    """
    if operation == "queryItems":
        partition_key = event.get("id")
        response = query_items(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            key_condition_expression="#id = :_id",
            expression_attribute_names={
                "#id": "_id",
            },
            expression_attribute_values={
                ":_id": {
                    "S": partition_key,
                }
            },
            logger=logger,
        )
        return {
            "statusCode": response["ResponseMetadata"]["HTTPStatusCode"],
            "isBase64Encoded": False,
            "body": {
                "items": response["items"],
            },
        }

    """
    Example of delete_item
    #################################################################
    """
    if operation == "deleteItem":
        partition_key = event.get("id")
        response = get_item(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            key={
                "_id": {
                    "S": partition_key,
                }
            },
            logger=logger,
        )

        if not response:
            return {
                "statusCode": 400,
                "isBase64Encoded": False,
                "body": {
                    "message": "No matching item found",
                },
            }

        response = delete_item(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            key={
                "_id": {
                    "S": partition_key,
                }
            },
            logger=logger,
        )
        status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        message = "Item deleted successfully"
        if status_code != 200:
            status_code = 400
            message = "Failed to delete item, see CloudWatch logs for details."

        return {
            "statusCode": status_code,
            "isBase64Encoded": False,
            "body": {"message": message, "deletedItem": response["deletedItem"]},
        }

    """
    Example of scan_items
    ###################################################################
    """
    if operation == "scanItems":
        partition_key = event.get("id")
        response = scan_items(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            filter_expression="#id = :_id",
            expression_attribute_names={
                "#id": "_id",
                "#name": "Name",
                "#email": "Email",
                "#address": "Address",
                "#phone": "Phone",
            },
            expression_attribute_values={
                ":_id": {
                    "S": partition_key,
                }
            },
            projection_expression="#id,#name,#email,#address,#phone",
            logger=logger,
        )

        status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        message = None
        if status_code != 200:
            status_code = 400
            message = "No items found."

        return {
            "statusCode": status_code,
            "isBase64Encoded": False,
            "body": {
                "items": message or response["items"],
            },
        }

    """
    Example of get_item_count
    ###################################################################
    """
    if operation == "itemCount":
        response = get_item_count(
            dynamodb_client=dynamodb_client,
            table_name=DYNAMODB_TABLE_NAME,
            logger=logger,
        )
        message = None
        status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if status_code != 200:
            status_code = 400
            message = "Failed to get item count, see CloudWatch logs for details."

        return {
            "statusCode": status_code,
            "isBase64Encoded": False,
            "body": {"itemCount": message or response["Table"]["ItemCount"]},
        }
